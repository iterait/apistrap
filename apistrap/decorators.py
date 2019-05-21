from __future__ import annotations

import abc
import inspect
from functools import wraps
from typing import TYPE_CHECKING, Callable, Optional, Sequence, Type, Union

from schematics import Model
from schematics.exceptions import DataError

from apistrap.errors import ApiClientError, InvalidFieldsError
from apistrap.examples import ExamplesMixin, model_examples_to_openapi_dict
from apistrap.schematics_converters import schematics_model_to_schema_object
from apistrap.tags import TagData
from apistrap.types import FileResponse

if TYPE_CHECKING:
    from apistrap.extension import Apistrap


def _ensure_specs_dict(func: Callable):
    if not hasattr(func, "specs_dict"):
        func.specs_dict = {"parameters": [], "responses": {}}


def _add_ignored_param(func: Callable, arg: str):
    if not hasattr(func, "_ignored_params"):
        setattr(func, "_ignored_params", [])

    func._ignored_params.append(arg)


def _get_wrapped_function(func: Callable):
    """
    Get the actual function from a decorated function. This could end up in a loop on horribly mangled functions.
    """

    wrapped = getattr(func, "__wrapped__", None)

    if wrapped is None:
        return func

    return _get_wrapped_function(wrapped)


class IgnoreParamsDecorator:
    """
    A decorator that marks specified function parameters as ignored for the purposes of generating a specification
    """

    def __init__(self, ignored_params: Sequence[str]):
        self._ignored_params = ignored_params

    def __call__(self, wrapped_func):
        for param in self._ignored_params:
            _add_ignored_param(wrapped_func, param)
        return wrapped_func


class RespondsWithDecorator:
    """
    A decorator that fills in response schemas in the Swagger specification. It also converts Schematics models returned
    by view functions to JSON and validates them.
    """

    outermost_decorators = {}
    """
    Maps functions to the outermost RespondsWithDecorator so that we can perform checks for unknown response classes 
    when we get to the last decorator
    """

    def __init__(
        self,
        apistrap: Apistrap,
        response_class: Type[Model],
        *,
        code: int = 200,
        description: Optional[str] = None,
        mimetype: Optional[str] = None,
    ):
        self._response_class = response_class
        self._code = code
        self._apistrap = apistrap
        self._description = description or self._response_class.__name__
        self._mimetype = mimetype

    def __call__(self, wrapped_func: Callable):
        _ensure_specs_dict(wrapped_func)

        if self._response_class == FileResponse:
            wrapped_func.specs_dict["responses"][str(self._code)] = {
                "description": self._description or self._response_class.__name__,
                "content": {
                    self._mimetype or "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
                },
            }
        else:
            wrapped_func.specs_dict["responses"][str(self._code)] = {
                "description": self._description or self._response_class.__name__,
                "content": {"application/json": {"schema": self._get_schema_object()}},
            }

            if issubclass(self._response_class, ExamplesMixin):
                # fmt: off
                wrapped_func.specs_dict["responses"][str(self._code)]["content"]["application/json"]["examples"] = \
                    model_examples_to_openapi_dict(self._response_class)
                # fmt: on

        innermost_func = _get_wrapped_function(wrapped_func)
        self.outermost_decorators[innermost_func] = self

        if inspect.iscoroutinefunction(wrapped_func):

            @wraps(wrapped_func)
            async def wrapper(*args, **kwargs):
                response = await wrapped_func(*args, **kwargs)
                is_last_decorator = self.outermost_decorators[innermost_func] == self
                return await self._process_response(response, is_last_decorator, *args, **kwargs)

        else:

            @wraps(wrapped_func)
            def wrapper(*args, **kwargs):
                response = wrapped_func(*args, **kwargs)
                is_last_decorator = self.outermost_decorators[innermost_func] == self
                return self._process_response(response, is_last_decorator)

        return wrapper

    def _get_schema_object(self):
        return schematics_model_to_schema_object(self._response_class, self._apistrap)

    def _process_response(self, response, is_last_decorator: bool, *args, **kwargs):
        """
        Process a response received from an endpoint handler (i.e. send it)
        :param response: the response to be processed
        :param is_last_decorator: True if the current decorator is the outermost one
        """


class AcceptsDecorator(metaclass=abc.ABCMeta):
    """
    A decorator that validates request bodies against a schema and passes it as an argument to the view function.
    The destination argument must be annotated with the request type.
    """

    def __init__(self, apistrap: Apistrap, request_class: Type[Model]):
        self._apistrap = apistrap
        self._request_class = request_class

    def _find_parameter_by_request_class(self, signature: inspect.Signature) -> Optional[inspect.Parameter]:
        for parameter in signature.parameters.values():
            if isinstance(parameter.annotation, str):
                if parameter.annotation == self._request_class.__qualname__:
                    return parameter
            elif isinstance(parameter.annotation, type):
                if issubclass(self._request_class, parameter.annotation):
                    return parameter
        return None

    def __call__(self, wrapped_func: Callable):
        _ensure_specs_dict(wrapped_func)

        # TODO parse title from param in docblock
        wrapped_func.specs_dict["requestBody"] = {
            "content": {
                "application/json": {"schema": schematics_model_to_schema_object(self._request_class, self._apistrap)}
            },
            "required": True,
        }

        if issubclass(self._request_class, ExamplesMixin):
            # fmt: off
            wrapped_func.specs_dict["requestBody"]["content"]["application/json"]["examples"] = \
                model_examples_to_openapi_dict(self._request_class)
            # fmt: on

        wrapped_func.specs_dict["x-codegen-request-body-name"] = "body"

        signature = inspect.signature(wrapped_func)
        request_arg = self._find_parameter_by_request_class(signature)

        if request_arg is None:
            raise TypeError(f"no argument of type `{self._request_class}` found")

        if inspect.iscoroutinefunction(wrapped_func):

            @wraps(wrapped_func)
            async def wrapper(*args, **kwargs):
                self._check_request_type(*args, **kwargs)
                body = await self._get_request_json(*args, **kwargs)
                kwargs = self._process_request_kwargs(body, signature, request_arg, *args, **kwargs)
                return await wrapped_func(*args, **kwargs)

        else:

            @wraps(wrapped_func)
            def wrapper(*args, **kwargs):
                self._check_request_type(*args, **kwargs)
                body = self._get_request_json()
                kwargs = self._process_request_kwargs(body, signature, request_arg, *args, **kwargs)
                return wrapped_func(*args, **kwargs)

        _add_ignored_param(wrapper, request_arg.name)
        return wrapper

    def _check_request_type(self, *args, **kwargs):
        if self._get_request_content_type(*args, **kwargs) != "application/json":
            raise ApiClientError("Unsupported media type, JSON is expected")

    def _process_request_kwargs(self, body, signature, request_arg, *args, **kwargs):
        bound_args = signature.bind_partial(*args, **kwargs)
        if request_arg.name not in bound_args.arguments:
            request_object = self._request_class.__new__(self._request_class)

            try:
                request_object.__init__(body, validate=True, partial=False, strict=True)
            except DataError as e:
                raise InvalidFieldsError(e.errors) from e

            new_kwargs = {request_arg.name: request_object}
            new_kwargs.update(**kwargs)
            return new_kwargs

    @abc.abstractmethod
    def _get_request_content_type(self, *args, **kwargs) -> str:
        """
        Get the value of the Content-Type header of current request
        """

    @abc.abstractmethod
    def _get_request_json(self, *args, **kwargs):
        """
        Get the JSON content of the request
        """


class AcceptsFileDecorator:
    """
    A decorator used to declare that an endpoint accepts a file upload in the request body.
    """

    def __init__(self, mime_type: str = None):
        self.mime_type = mime_type or "application/octet-stream"

    def __call__(self, wrapped_func: Callable):
        _ensure_specs_dict(wrapped_func)

        wrapped_func.specs_dict["requestBody"] = {
            "content": {self.mime_type: {"schema": {"type": "string", "format": "binary"}}},
            "required": True,
        }

        return wrapped_func


class IgnoreDecorator:
    """
    A decorator that marks an endpoint as ignored so that the extension won't include it in the specification.
    """

    def __call__(self, wrapped_func: Callable):
        wrapped_func.apistrap_ignore = True
        return wrapped_func


class TagsDecorator:
    """
    A decorator that adds tags to the OpenAPI specification of the decorated view function.
    """

    def __init__(self, extension: Apistrap, tags: Sequence[Union[str, TagData]]):
        self._tags = tags
        self._extension = extension

    def __call__(self, wrapped_func: Callable):
        _ensure_specs_dict(wrapped_func)
        wrapped_func.specs_dict.setdefault("tags", [])

        for tag in self._tags:
            wrapped_func.specs_dict["tags"].append(tag.name if isinstance(tag, TagData) else tag)

            if isinstance(tag, TagData):
                self._extension.add_tag_data(tag)

        return wrapped_func


class SecurityDecorator:
    """
    A decorator that enforces user authentication and authorization.
    """

    def __init__(self, extension: Apistrap, scopes: Sequence[str]):
        self._extension = extension
        self._scopes = scopes

    def __call__(self, wrapped_func: Callable):
        _ensure_specs_dict(wrapped_func)
        wrapped_func.specs_dict.setdefault("security", [])

        for scheme in self._extension.security_schemes:
            wrapped_func.specs_dict["security"].append({scheme.name: [*map(str, self._scopes)]})

            wrapped_func = scheme.enforcer(self._scopes)(wrapped_func)

        return wrapped_func
