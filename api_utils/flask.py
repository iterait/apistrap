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

    def autodoc(self, *, ignored_args: Sequence[str] = ()):
        return AutodocDecorator(self, ignored_args=ignored_args)

    def responds_with(self, response_class: Type[Model], *, code: int = 200):
        return RespondsWithDecorator(self, response_class, code=code)

    def accepts(self, request_class: Type[Model]):
        return AcceptsDecorator(self, request_class)

    def tags(self, *tags: str):
        return TagsDecorator(tags)

    def add_definition(self, name: str, schema: dict) -> str:
        definition_name = "#/definitions/{}".format(name)

        if name in self.config["definitions"]:
            if self.config["definitions"][name] != schema:
                raise ValueError("Conflicting definitions of `{}`".format(definition_name))
        else:
            self.config["definitions"][name] = schema

        return definition_name
