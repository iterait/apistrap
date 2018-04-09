from inspect import signature
from typing import Type
from schematics import Model

import api_utils.flask
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
