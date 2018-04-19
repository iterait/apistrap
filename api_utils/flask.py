from typing import Type, Sequence

from flasgger import Swagger as Flasgger
from schematics import Model

from api_utils.decorators import AutodocDecorator, RespondsWithDecorator, AcceptsDecorator, TagsDecorator


class Swagger(Flasgger):
    def __init__(self, app=None, config=None):
        config = config or self.DEFAULT_CONFIG.copy()
        config.setdefault("definitions", {})
        super().__init__(app, config)

    @property
    def title(self) -> str:
        return self.config.get("title")

    @title.setter
    def title(self, title: str):
        self.config["title"] = title

    @property
    def description(self) -> str:
        return self.config.get("description")

    @description.setter
    def description(self, description: str):
        self.config["description"] = description

    def autodoc(self, *, ignored_args: Sequence[str] =()):
        return AutodocDecorator(self, ignored_args=ignored_args)

    def responds_with(self, response_class: Type[Model], *, code: int =200):
        return RespondsWithDecorator(self, response_class, code=code)

    def accepts(self, request_class: Type[Model]):
        return AcceptsDecorator(self, request_class)

    def tags(self, *tags: str):
        return TagsDecorator(tags)

    def add_definition(self, name: str, schema: dict) -> str:
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
