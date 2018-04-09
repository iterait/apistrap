from typing import Type

from flasgger import Swagger as Flasgger
from schematics import Model

from api_utils.decorators import AutodocDecorator, RespondsWithDecorator


class Swagger(Flasgger):
    def __init__(self, app=None, config=None):
        config = config or self.DEFAULT_CONFIG.copy()
        config.setdefault("definitions", {})
        super().__init__(app, config)

    def autodoc(self, *, ignored_args=()):
        return AutodocDecorator(self, ignored_args=ignored_args)

    def responds_with(self, response_class: Type[Model], *, code=200):
        return RespondsWithDecorator(self, response_class, code=code)

    def add_definition(self, name, schema):
        definition_prefix = "#/definitions/"
        i = 0

        while True:
            i += 1
            definition_name = name

            if i > 1:
                definition_name += "_" + str(i)

            if definition_name in self.config["definitions"].keys():
                if self.config["definitions"][definition_name] == schema:
                    return definition_prefix + definition_name
            else:
                self.config["definitions"][definition_name] = schema
                return definition_prefix + definition_name
