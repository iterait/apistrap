from functools import wraps
from inspect import signature
from typing import Type, Sequence

from flask import request
from schematics import Model
from schematics.exceptions import DataError

import api_utils.flask
from api_utils.errors import ApiClientError, InvalidFieldsError
from api_utils.schematics_utils import schema_object_for_model


def _ensure_specs_dict(func):
    if not hasattr(func, "specs_dict"):
        func.specs_dict = {
            "parameters": [],
            "responses": {}
        }


class AutodocDecorator:
    """
    A decorator that generates Swagger metadata based on the signature of the decorated function and black magic.
    The metadata is collected by Flasgger and used to generate API specs/docs.
    """

    type_map = {
        int: "integer",
        str: "string"
    }

    def __init__(self, swagger: 'api_utils.flask.Swagger', *, ignored_args=()):
        self.ignored_args = ignored_args

    def __call__(self, wrapped_func):
        _ensure_specs_dict(wrapped_func)
        sig = signature(wrapped_func)

        for arg in sig.parameters.values():
            if arg.name not in self.ignored_args:
                param_data = {
                    "in": "path",
                    "name": arg.name
                }

                if arg.annotation in self.type_map:
                    param_data["type"] = self.type_map[arg.annotation]

                wrapped_func.specs_dict["parameters"].append(param_data)

        return wrapped_func


class RespondsWithDecorator:
    """
    A decorator that fills in response schemas in the Swagger specification.
    """

    def __init__(self, swagger: 'api_utils.flask.Swagger', response_class: Type[Model], *, code=200):
        self.response_class = response_class
        self.code = code
        self.swagger = swagger

    def __call__(self, wrapped_func):
        _ensure_specs_dict(wrapped_func)

        wrapped_func.specs_dict["responses"][str(self.code)] = {
            "$ref": self.swagger.add_definition(self.response_class.__name__, self._get_schema_object())
        }

        return wrapped_func

    def _get_schema_object(self):
        return schema_object_for_model(self.response_class)


class AcceptsDecorator:
    """
    A decorator that validates request bodies against a schema and passes it as an argument to the view function.
    The destination argument must be annotated with the request type.
    """

    def __init__(self, swagger: 'api_utils.flask.Swagger', request_class: Type[Model]):
        self.swagger = swagger
        self.request_class = request_class

    def __call__(self, wrapped_func):
        _ensure_specs_dict(wrapped_func)

        wrapped_func.specs_dict["parameters"].append({
            "in": "body",
            "name": "body",
            "required": True,
            "schema": {
                "$ref": self.swagger.add_definition(self.request_class.__name__, schema_object_for_model(self.request_class))
            }
        })

        sig = signature(wrapped_func)
        request_arg = next(filter(lambda arg: issubclass(self.request_class, arg.annotation), sig.parameters.values()), None)

        if request_arg is None:
            raise TypeError("no argument of type {} found".format(self.request_class))

        @wraps(wrapped_func)
        def wrapper(*args, **kwargs):
            if request.content_type != "application/json":
                raise ApiClientError("Unsupported media type")

            bound_args = sig.bind_partial(*args, **kwargs)
            if request_arg.name not in bound_args.arguments:
                request_object = self.request_class.__new__(self.request_class)

                try:
                    request_object.__init__(request.json, validate=True, partial=False, strict=True)
                except DataError as e:
                    raise InvalidFieldsError(e.errors) from e

                new_kwargs = {request_arg.name: request_object}
                new_kwargs.update(**kwargs)
                kwargs = new_kwargs

            return wrapped_func(*args, **kwargs)

        return wrapper


class TagsDecorator:
    """
    A decorator that adds tags to the OpenAPI specification of the decorated view function.
    """

    def __init__(self, tags: Sequence[str]):
        self.tags = tags

    def __call__(self, wrapped_func):
        _ensure_specs_dict(wrapped_func)
        wrapped_func.specs_dict.setdefault("tags", [])
        wrapped_func.specs_dict["tags"].extend(self.tags)
        return wrapped_func
