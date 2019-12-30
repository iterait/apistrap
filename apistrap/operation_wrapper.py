from __future__ import annotations

import abc
import inspect
from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from typing import TYPE_CHECKING, Callable, Dict, Generator, Optional, Sequence, Tuple, Type, TypeVar, Union, cast

from docstring_parser import parse as parse_doc
from docstring_parser.common import DocstringParam
from schematics import Model
from schematics.exceptions import DataError

from apistrap.decorators import (
    AcceptsDecorator,
    AcceptsFileDecorator,
    AcceptsQueryStringDecorator,
    IgnoreParamsDecorator,
    RespondsWithDecorator,
    SecurityDecorator,
    TagsDecorator,
)
from apistrap.errors import InvalidFieldsError, InvalidResponseError, UnexpectedResponseError
from apistrap.examples import ExamplesMixin, model_examples_to_openapi_dict
from apistrap.schemas import ErrorResponse
from apistrap.schematics_converters import schematics_model_to_schema_object
from apistrap.tags import TagData
from apistrap.types import FileResponse
from apistrap.utils import resolve_fw_decl, snake_to_camel

if TYPE_CHECKING:  # pragma: no cover
    from apistrap.extension import Apistrap, SecurityScheme


@dataclass(frozen=True)
class ResponseData:
    description: Optional[str] = None
    mimetype: Optional[str] = None


DecoratorType = TypeVar("DecoratorType")


class OperationWrapper(metaclass=abc.ABCMeta):
    """
    Extracts metadata from a view handler function and uses it to 1) generate an OpenAPI specification and 2) implement
    behavior specified by Apistrap decorators.
    """

    def __init__(self, extension: Apistrap, function: Callable, decorators: Sequence[object]):
        """
        Initialize an operation wrapper

        :param extension: The extension that instantiated the wrapper
        :param function: The view handler function to be processed
        :param decorators: The decorators present on the function
        """
        self._responses: Dict[Type[Model], Dict[int, ResponseData]] = defaultdict(lambda: {})
        self._request_body_class: Optional[Type[Model]] = None
        self._request_body_parameter: Optional[str] = None
        self._request_body_file_type: Optional[str] = None
        self._request_body_content_types: Optional[Sequence[str]] = None
        self._path_parameters: Dict[str, Type] = {}
        self._query_parameters: Dict[str, Type] = {}
        self._security: Dict[str, Sequence[str]] = {}
        self._tags: Sequence[str] = []

        self._wrapped_function: Callable = function
        self._decorators: Sequence[object] = decorators
        self._extension = extension
        self._doc = parse_doc(function.__doc__)
        self._signature = inspect.signature(function)

        self.process_metadata()

    def process_metadata(self):
        """
        Load metadata from the view handler function.
        """

        self._responses = self._get_responses()

        (
            self._request_body_parameter,
            self._request_body_class,
            self._request_body_content_types,
        ) = self._get_request_body_parameter()

        if self._request_body_content_types is None:
            self._request_body_content_types = ["application/json"]

        self._request_body_file_type = self._get_request_body_file_type()
        if self._request_body_parameter is not None and self._request_body_file_type is not None:
            raise TypeError("An endpoint cannot accept both a file and a model")

        self._query_parameters = dict(self._get_query_string_parameters())
        self._path_parameters = dict(self._get_path_parameters())

        self._security = [*self._get_security_requirements()]
        self._tags = [*self._get_tags()]

    ##############
    # Public API #
    ##############

    def get_openapi_spec(self):
        """
        Get an OpenAPI Operation object that describes the underlying endpoint.
        """

        spec = {"operationId": snake_to_camel(self._wrapped_function.__name__), "responses": {}}

        if self._doc.short_description:
            spec["summary"] = self._doc.short_description

        if self._doc.long_description:
            spec["description"] = self._doc.long_description

        if self._tags:
            spec["tags"] = self._tags

        if self._path_parameters or self._query_parameters:
            spec["parameters"] = []

        for name, param_type in self._path_parameters.items():
            if self._is_param_ignored(name):
                continue

            param_spec = {
                "name": name,
                "in": "path",
                "required": True,
                "schema": {"type": self._extension.PARAMETER_TYPE_MAP.get(param_type, "string")},
            }

            param_doc = self._get_param_doc(name)
            if param_doc is not None:
                param_spec["description"] = param_doc.description

            spec["parameters"].append(param_spec)

        for name, param_type in self._query_parameters.items():
            param_refl: inspect.Parameter = self._signature.parameters[name]
            param_spec = {
                "name": name,
                "in": "query",
                "required": param_refl.default == inspect.Parameter.empty,
                "schema": {"type": self._extension.PARAMETER_TYPE_MAP.get(param_type, "string")},
            }

            param_doc = self._get_param_doc(name)
            if param_doc is not None:
                param_spec["description"] = param_doc.description

            spec["parameters"].append(param_spec)

        if self._request_body_parameter:
            mimetypes = self._request_body_content_types

            spec["requestBody"] = {
                "content": {
                    mimetype: {"schema": schematics_model_to_schema_object(self._request_body_class, self._extension)}
                    for mimetype in mimetypes
                },
                "required": True,
            }

            if issubclass(self._request_body_class, ExamplesMixin):
                for mimetype in mimetypes:
                    spec["requestBody"]["content"][mimetype]["examples"] = model_examples_to_openapi_dict(
                        self._request_body_class
                    )

            param_doc = self._get_param_doc(self._request_body_parameter)
            if param_doc is not None and param_doc.description:
                spec["requestBody"]["description"] = param_doc.description

            spec["x-codegen-request-body-name"] = "body"
        elif self._request_body_file_type:
            spec["requestBody"] = {
                "content": {self._request_body_file_type: {"schema": {"type": "string", "format": "binary"}}}
            }

        if self._security:
            spec["security"] = self._security

        for response_class, codes in self._responses.items():
            for code, response_data in codes.items():
                if issubclass(response_class, FileResponse):
                    mime = response_data.mimetype or "application/octet-stream"
                    spec["responses"][str(code)] = {
                        "description": response_data.description or response_class.__name__,
                        "content": {mime: {"schema": {"type": "string", "format": "binary"}}},
                    }
                else:
                    spec["responses"][str(code)] = {
                        "description": response_data.description or response_class.__name__,
                        "content": {
                            "application/json": {
                                "schema": schematics_model_to_schema_object(response_class, self._extension)
                            }
                        },
                    }

                    if issubclass(response_class, ExamplesMixin):
                        # fmt: off
                        spec["responses"][str(code)]["content"]["application/json"]["examples"] = \
                            model_examples_to_openapi_dict(response_class)
                        # fmt: on

        return spec

    @abc.abstractmethod
    def get_decorated_function(self):
        """
        Return the view handler decorated with functionality added by Apistrap.
        """

    ######################################
    # Extension points for child classes #
    ######################################

    @abc.abstractmethod
    def is_raw_response(self, response: object) -> bool:
        """
        Check whether the response is raw (which would mean it doesn't need postprocessing).

        :param response: the response to be checked
        :return: True if the response is raw, False otherwise
        """

    #############################
    # Helpers for child classes #
    #############################

    @property
    def accepts_body(self):
        """
        Does the underlying endpoint accept a body parameter
        """
        return self._request_body_parameter is not None

    def _load_request_body(self, body_primitive) -> Dict[str, Model]:
        """
        Load the request body as an object with a fixed schema from a primitive data object (dict structure).

        :param body_primitive: the request body as a primitive object
        :return: the request body as an object of a request class
        """
        if self._request_body_parameter is None or self._request_body_class is None:
            raise ValueError("The endpoint doesn't accept a request body")

        body = self._request_body_class.__new__(self._request_body_class)

        try:
            body.__init__(body_primitive, validate=True, partial=False, strict=True)
        except DataError as ex:
            raise InvalidFieldsError(ex.errors) from ex

        return {self._request_body_parameter: body}

    def _get_required_scopes(self) -> Generator[Tuple[SecurityScheme, Sequence[str]]]:
        """
        Get a list of scopes required by the endpoint.
        """
        for security_decorator in self._find_decorators(SecurityDecorator):
            if (
                len(self._extension.security_schemes) > 1
                and self._extension.default_security_scheme is None
                and security_decorator.security_scheme is None
            ):
                raise TypeError(
                    "Multiple security schemes are defined and no default is set - cannot use security decorator without an explicit scheme"
                )

            if len(self._extension.security_schemes) == 0:
                raise TypeError("At least one security scheme must be defined in order to use the security decorator")

            scheme = (
                security_decorator.security_scheme
                or self._extension.default_security_scheme
                or self._extension.security_schemes[0]
            )
            yield scheme, security_decorator.scopes

    def _postprocess_response(self, response: Union[Model, Tuple[Model, int]]) -> Tuple[Model, int, Optional[str]]:
        """
        Check response type and code and add the code if necessary.
        
        :param response: response received from a view handler
        :return: a response and status code
        """
        code = None

        if isinstance(response, tuple):
            response, code = response

        if self.is_raw_response(response):
            return response, code or 200, ""

        if type(response) not in self._responses.keys():
            raise UnexpectedResponseError(type(response))

        if code is None:
            if len(self._responses[type(response)]) > 1:
                raise InvalidResponseError({"status_code": ["Missing status code"]})
            code = next(iter(self._responses[type(response)].keys()))

        if code not in self._responses[type(response)].keys():
            raise UnexpectedResponseError(type(response), code)

        if isinstance(response, Model):
            try:
                response.validate()
            except DataError as ex:
                raise InvalidResponseError(ex.errors) from ex

        return response, code, self._responses[type(response)][code].mimetype

    def _get_param_doc(self, param_name: str) -> Optional[DocstringParam]:
        """
        Get parameter documentation from the docblock of the underlying view handler function.

        :param param_name: name of the parameter
        :return: the parameter documentation
        """
        for param in self._doc.params:
            if param.arg_name == param_name:
                return param

        return None

    ###################################
    # Extraction of endpoint metadata #
    ###################################

    def _find_decorators(self, decorator_class: Type[DecoratorType]) -> Generator[DecoratorType, None, None]:
        """
        Look up decorators of the view handler by type.
        """
        for decorator in self._decorators:
            if isinstance(decorator, decorator_class):
                yield decorator

    def _get_responses(self):
        """
        Find all possible response classes and codes for the underyling endpoint.
        """
        result: Dict[Type[Model], Dict[int, ResponseData]] = defaultdict(lambda: {})

        for response_class, code, data in chain(
            self._get_response_from_annotation(),
            self._get_responses_from_decorators(),
            self._get_responses_from_raises(),
        ):
            if code in result[response_class].keys():
                raise TypeError("Multiple responses declared with the same schema and code")

            result[response_class][code] = data

        return result

    def _get_response_from_annotation(self) -> Generator[Tuple[Type[Model], int, ResponseData], None, None]:
        """
        Get the response class specified by the return value annotation of the view handler.
        """
        annotation = self._signature.return_annotation

        if annotation is inspect.Signature.empty:
            return

        annotation = resolve_fw_decl(self._wrapped_function, annotation)

        if not issubclass(annotation, Model):
            raise TypeError("Unsupported return type")

        yield annotation, 200, ResponseData(self._doc.returns.description if self._doc.returns else None)

    def _get_responses_from_decorators(self) -> Generator[Tuple[Type[Model], int, ResponseData], None, None]:
        """
        Get the response classes specified by @responds_with decorators.
        """
        for decorator in self._find_decorators(RespondsWithDecorator):
            yield decorator.response_class, decorator.code, ResponseData(decorator.description, decorator.mimetype)

    def _get_responses_from_raises(self) -> Generator[Tuple[Type[Model], int, ResponseData], None, None]:
        """
        Get response classes specified by 'raises' blocks in the docblock of the view handler.
        """
        for item in self._doc.raises:
            exception_type = cast(Type[Exception], resolve_fw_decl(self._wrapped_function, item.type_name))
            code = self._extension.exception_to_http_code(exception_type)

            if code is None:
                continue

            yield ErrorResponse, code, ResponseData(item.description)

    def _get_request_body_parameter(self) -> Union[Tuple[str, Type, Optional[Sequence[str]]], Tuple[None, None, None]]:
        """
        Get the name and type of the parameter used to pass the request body to the view handler and a list of content
        types supported by the handler.
        """
        accepts_decorator = None

        for decorator in self._find_decorators(AcceptsDecorator):
            if accepts_decorator is not None:
                raise TypeError("Multiple @accepts decorators")

            accepts_decorator = decorator

        body_param: Optional[inspect.Parameter] = None
        param: inspect.Parameter
        for param in self._signature.parameters.values():
            annotation = resolve_fw_decl(self._wrapped_function, param.annotation)
            matches_decorator = accepts_decorator and accepts_decorator.request_class == annotation
            is_model = (not accepts_decorator) and issubclass(annotation, Model)

            if matches_decorator or is_model:
                if body_param is not None:
                    if not accepts_decorator:
                        raise TypeError(
                            "Multiple candidates for request body injection. Use @accepts to specify which one should be used."
                        )
                    else:
                        raise TypeError(
                            f"Multiple parameters of type `{accepts_decorator.request_class.__name__}` specified by @accepts"
                        )

                body_param = param

        if body_param is None:
            if accepts_decorator:
                raise TypeError("No parameter for request body injection")

            return None, None, None

        return (
            body_param.name,
            resolve_fw_decl(self._wrapped_function, body_param.annotation),
            accepts_decorator.mimetypes if accepts_decorator else None,
        )

    def _get_request_body_file_type(self) -> Optional[str]:
        """
        If the endpoint accepts files, get the supported types.
        """
        result = None
        for decorator in self._find_decorators(AcceptsFileDecorator):
            if result is not None:
                raise TypeError("An endpoint cannot accept files of multiple types")

            result = decorator.mime_type

        return result

    def _get_query_string_parameters(self) -> Generator[Tuple[str, Type], None, None]:
        """
        Get names and types of parameters accepted by the endpoint via query string.
        """
        for decorator in self._find_decorators(AcceptsQueryStringDecorator):
            for param in decorator.parameter_names:
                if param not in self._signature.parameters:
                    raise TypeError(f"Unknown parameter `{param}`")

                param_refl: inspect.Parameter = self._signature.parameters[param]
                annotation = resolve_fw_decl(self._wrapped_function, param_refl.annotation)

                if annotation not in (str, int):
                    raise TypeError("Only string and integer query parameters are supported")

                yield param, annotation

    def _get_path_parameters(self) -> Generator[Tuple[str, Type], None, None]:
        """
        Get a list of path parameters accepted by the wrapped endpoint.
        """

    def _get_security_requirements(self) -> Generator[Dict[str, Sequence[str]], None, None]:
        """
        Get a security requirement specification from the endpoint.
        """
        for decorator in self._find_decorators(SecurityDecorator):
            scheme = decorator.security_scheme or self._extension.default_security_scheme

            if scheme is None and len(self._extension.security_schemes) == 1:
                scheme = self._extension.security_schemes[0]

            if scheme is None:
                raise TypeError("No security scheme found")

            yield {scheme.name: [*map(str, decorator.scopes)]}

    def _get_tags(self) -> Generator[str, None, None]:
        """
        Get endpoint tags (used in the specification to group similar endpoints).
        """
        for decorator in self._find_decorators(TagsDecorator):
            for tag in decorator.tags:
                if isinstance(tag, TagData):
                    self._extension.add_tag_data(tag)
                yield str(tag)

    def _is_param_ignored(self, param_name: str) -> bool:
        """
        Should a parameter be ignored when generating the specification?
        """
        for decorator in self._find_decorators(IgnoreParamsDecorator):
            for ignored_param in decorator.ignored_params:
                if ignored_param == param_name:
                    return True

        return False
