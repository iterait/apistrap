import inspect
from functools import wraps
from typing import Type, Sequence, Callable, Optional

from flask import request, jsonify, Response, send_file
from schematics import Model
from schematics.exceptions import DataError

import apistrap.flask
from apistrap.errors import ApiClientError, InvalidFieldsError, InvalidResponseError, UnexpectedResponseError
from apistrap.schematics_converters import schematics_model_to_schema_object
from apistrap.types import FileResponse


def _ensure_specs_dict(func: Callable):
    if not hasattr(func, "specs_dict"):
        func.specs_dict = {
            "parameters": [],
            "responses": {}
        }


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


class AutodocDecorator:
    """
    A decorator that generates Swagger metadata based on the signature of the decorated function and black magic.
    The metadata is collected by Flasgger and used to generate API specs/docs.
    """

    TYPE_MAP = {
        int: "integer",
        str: "string"
    }

    def __init__(self, swagger: 'apistrap.flask.Swagger', *, ignored_args: Sequence[str] = ()):
        self._ignored_args = ignored_args

    def __call__(self, wrapped_func: Callable):
        _ensure_specs_dict(wrapped_func)
        signature = inspect.signature(wrapped_func)
        ignored = list(self._ignored_args)
        ignored += getattr(wrapped_func, "_ignored_params", [])

        for arg in signature.parameters.values():
            if arg.name not in ignored:
                param_data = {
                    "in": "path",
                    "name": arg.name
                }

                if arg.annotation in AutodocDecorator.TYPE_MAP:
                    param_data["type"] = AutodocDecorator.TYPE_MAP[arg.annotation]

                wrapped_func.specs_dict["parameters"].append(param_data)

        wrapped_func.specs_dict["operationId"] = self._snake_to_camel(wrapped_func.__name__)

        return wrapped_func

    @staticmethod
    def _snake_to_camel(value):
        """
        Convert a string from snake_case to camelCase
        """
        result = ''.join(x.capitalize() or '_' for x in value.split('_'))
        return result[0].lower() + result[1:]


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

    def __init__(self, swagger: 'apistrap.flask.Swagger', response_class: Type[Model], *,
                 code: int=200, description: Optional[str]=None, mimetype: Optional[str]=None):
        self._response_class = response_class
        self._code = code
        self._swagger = swagger
        self._description = description or self._response_class.__name__
        self._mimetype = mimetype

    def __call__(self, wrapped_func: Callable):
        _ensure_specs_dict(wrapped_func)

        if self._response_class == FileResponse:
            wrapped_func.specs_dict["responses"][str(self._code)] = {
                "schema": {'type': 'file'},
                "description": self._description
            }
            if self._mimetype is not None:
                wrapped_func.specs_dict["produces"] = self._mimetype
        else:
            wrapped_func.specs_dict["responses"][str(self._code)] = {
                "schema": {
                    "$ref": self._swagger.add_definition(self._response_class.__name__, self._get_schema_object())
                },
                "description": self._description
            }

        innermost_func = _get_wrapped_function(wrapped_func)
        self.outermost_decorators[innermost_func] = self

        @wraps(wrapped_func)
        def wrapper(*args, **kwargs):
            response = wrapped_func(*args, **kwargs)

            if isinstance(response, Response):
                return response
            if not isinstance(response, self._response_class):
                if self.outermost_decorators[innermost_func] == self:
                    raise UnexpectedResponseError(type(response))
                return response
            if isinstance(response, FileResponse):
                return send_file(filename_or_fp=response.filename_or_fp,
                                 mimetype=self._mimetype,
                                 as_attachment=response.as_attachment,
                                 attachment_filename=response.attachment_filename,
                                 add_etags=response.add_etags,
                                 cache_timeout=response.cache_timeout,
                                 conditional=response.conditional,
                                 last_modified=response.last_modified)

            try:
                response.validate()
            except DataError as e:
                raise InvalidResponseError(e.errors) from e

            response = jsonify(response.to_primitive())
            response.status_code = self._code
            return response

        return wrapper

    def _get_schema_object(self):
        return schematics_model_to_schema_object(self._response_class)


class AcceptsDecorator:
    """
    A decorator that validates request bodies against a schema and passes it as an argument to the view function.
    The destination argument must be annotated with the request type.
    """

    def __init__(self, swagger: 'apistrap.flask.Swagger', request_class: Type[Model]):
        self._swagger = swagger
        self._request_class = request_class

    def __call__(self, wrapped_func: Callable):
        _ensure_specs_dict(wrapped_func)

        wrapped_func.specs_dict["parameters"].append({
            "in": "body",
            "name": "body",
            "required": True,
            "schema": {
                "$ref": self._swagger.add_definition(self._request_class.__name__, schematics_model_to_schema_object(self._request_class))
            }
        })

        signature = inspect.signature(wrapped_func)
        request_arg = next(filter(lambda arg: issubclass(self._request_class, arg.annotation), signature.parameters.values()), None)

        if request_arg is None:
            raise TypeError("no argument of type {} found".format(self._request_class))

        @wraps(wrapped_func)
        def wrapper(*args, **kwargs):
            if request.content_type != "application/json":
                raise ApiClientError("Unsupported media type, JSON is expected")

            bound_args = signature.bind_partial(*args, **kwargs)
            if request_arg.name not in bound_args.arguments:
                request_object = self._request_class.__new__(self._request_class)

                try:
                    request_object.__init__(request.json, validate=True, partial=False, strict=True)
                except DataError as e:
                    raise InvalidFieldsError(e.errors) from e

                new_kwargs = {request_arg.name: request_object}
                new_kwargs.update(**kwargs)
                kwargs = new_kwargs

            return wrapped_func(*args, **kwargs)

        _add_ignored_param(wrapper, request_arg.name)
        return wrapper


class TagsDecorator:
    """
    A decorator that adds tags to the OpenAPI specification of the decorated view function.
    """

    def __init__(self, tags: Sequence[str]):
        self._tags = tags

    def __call__(self, wrapped_func: Callable):
        _ensure_specs_dict(wrapped_func)
        wrapped_func.specs_dict.setdefault("tags", [])
        wrapped_func.specs_dict["tags"].extend(self._tags)
        return wrapped_func
