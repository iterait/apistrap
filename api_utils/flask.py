from typing import Type, Sequence, Optional
from copy import deepcopy

from flasgger import Swagger as Flasgger
from schematics import Model

from api_utils.decorators import AutodocDecorator, RespondsWithDecorator, AcceptsDecorator, TagsDecorator
from api_utils.errors import SwaggerExtensionError


class Swagger(Flasgger):
    def __init__(self, app=None, config=None):
        config = config or deepcopy(self.DEFAULT_CONFIG)
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

    @property
    def spec_url(self) -> Optional[str]:
        if len(self.config["specs"]) == 0:
            return None
        return self.config["specs"][0]["route"]

    @spec_url.setter
    def spec_url(self, url: Optional[str]):
        self._ensure_no_app("You cannot configure the spec_url after binding the extension with Flask")

        if self.spec_url is None:
            self.config["specs"] = deepcopy(self.DEFAULT_CONFIG["specs"])

        if url is None:
            self.config["specs"] = []
            return

        self.config["specs"][0]["route"] = url

    @property
    def ui_url(self) -> Optional[str]:
        if not self.config["swagger_ui"]:
            return None

        return self.config["specs_route"]

    @ui_url.setter
    def ui_url(self, value: Optional[str]):
        self._ensure_no_app("You cannot change the UI url after binding the extension with Flask")

        if value is None:
            self.config["swagger_ui"] = False
            return

        self.config["swagger_ui"] = True
        self.config["specs_route"] = value

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

    def _ensure_no_app(self, message):
        if hasattr(self, "app") and self.app is not None:
            raise SwaggerExtensionError(message)
