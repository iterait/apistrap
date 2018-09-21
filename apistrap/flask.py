from copy import deepcopy
import logging
from typing import Type, Sequence, Optional

from flasgger import Swagger as Flasgger
from flask import Flask, jsonify, Response
from schematics import Model
from werkzeug.exceptions import HTTPException

from apistrap.decorators import AutodocDecorator, RespondsWithDecorator, AcceptsDecorator, TagsDecorator
from apistrap.errors import SwaggerExtensionError, ApiClientError, ApiServerError
from apistrap.schemas import ErrorResponse
from apistrap.utils import format_exception


class Swagger(Flasgger):
    """
    A Flask extension for semi-automatic generation of OpenAPI specifications on the fly, using view decorators
    """

    def __init__(self, app=None):
        self.config = deepcopy(self.DEFAULT_CONFIG)
        self.config.setdefault("definitions", {})
        self.spec_url = "/swagger.json"
        self._default_error_handlers = True
        super().__init__(app, self.config)

    def init_app(self, app: Flask, decorators=None) -> None:
        """
        Bind the extension to a Flask app
        :param app: the Flask app to bind to
        :param decorators: decorators that should be used to wrap the UI and specification views
        """
        if self.use_default_error_handlers:
            app.register_error_handler(HTTPException, self.http_error_handler)
            app.register_error_handler(ApiClientError, self.error_handler)
            app.register_error_handler(ApiServerError, self.internal_error_handler)
            app.register_error_handler(Exception, self.internal_error_handler)

        super().init_app(app, decorators)

    def http_error_handler(self, exception: HTTPException):
        """
        A handler for Flask HTTPException objects
        :param exception: the exception raised due to a client error
        :return: a response object
        """

        logging.exception(exception)
        return jsonify(ErrorResponse(dict(message=exception.description)).to_primitive()), exception.code

    def error_handler(self, exception):
        """
        The default handler for API client errors
        :param exception: the exception raised due to a client error
        :return: a response object
        """

        if self.app.debug:
            logging.exception(exception)
            error_response = ErrorResponse(dict(
                message=str(exception),
                debug_data=format_exception(exception)
            ))
        else:
            error_response = ErrorResponse(dict(message=str(exception)))

        return jsonify(error_response.to_primitive()), 400

    def internal_error_handler(self, exception):
        """
        The default handler for API server errors. It will hide the details when not in debug mode.
        :param exception: the exception raised due to a server error
        :return: a response object
        """

        logging.exception(exception)

        if self.app.debug:
            error_response = ErrorResponse(dict(
                message=str(exception),
                debug_data=format_exception(exception)
            ))
        else:
            error_response = ErrorResponse(dict(message="Internal server error"))

        return jsonify(error_response.to_primitive()), 500

    @property
    def title(self) -> str:
        """
        A title of the OpenAPI specification (the name of the API)
        """
        return self.config.get("title")

    @title.setter
    def title(self, title: str):
        self.config["title"] = title

    @property
    def description(self) -> str:
        """
        A longer description of the API used in the OpenAPI specification
        """
        return self.config.get("description")

    @description.setter
    def description(self, description: str):
        self.config["description"] = description

    @property
    def spec_url(self) -> Optional[str]:
        """
        The URL where the extension should serve the OpenAPI specification. If it is None, the specification is not
        served at all.
        """
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
        """
        The URL where the extension should serve the Swagger UI. If it is None, the UI is not served at all.
        """
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

    @property
    def use_default_error_handlers(self) -> bool:
        """
        A flag that indicates if the extension should register its error handlers when binding it with the Flask app
        """
        return self._default_error_handlers

    @use_default_error_handlers.setter
    def use_default_error_handlers(self, value: bool):
        self._ensure_no_app("You cannot change the error handler settings after binding the extension with Flask")
        self._default_error_handlers = value

    def autodoc(self, *, ignored_args: Sequence[str] = ()):
        """
        A decorator that generates Swagger metadata based on the signature of the decorated function and black magic.
        """
        return AutodocDecorator(self, ignored_args=ignored_args)

    def responds_with(self, response_class: Type[Model], *, code: int=200, description: Optional[str]=None,
                      mimetype: Optional[str]=None):
        """
        A decorator that fills in response schemas in the Swagger specification. It also converts Schematics models
        returned by view functions to JSON and validates them.
        """
        return RespondsWithDecorator(self, response_class, code=code, description=description, mimetype=mimetype)

    def accepts(self, request_class: Type[Model]):
        """
        A decorator that validates request bodies against a schema and passes it as an argument to the view function.
        The destination argument must be annotated with the request type.
        """
        return AcceptsDecorator(self, request_class)

    def tags(self, *tags: str):
        """
        A decorator that adds tags to the OpenAPI specification of the decorated view function.
        """
        return TagsDecorator(tags)

    def add_definition(self, name: str, schema: dict) -> str:
        """
        Add a new definition to the specification. If a different schema is supplied for an existing definition, a
        ValueError is raised.
        :param name: the name of the definition (without the '#/definitions/' part)
        :param schema: a JsonObject OpenAPI structure
        :return: the full path to the definition in the specification file (can be used directly with $ref)
        """

        definition_name = "#/definitions/{}".format(name)

        if name in self.config["definitions"]:
            if self.config["definitions"][name] != schema:
                raise ValueError("Conflicting definitions of `{}`".format(definition_name))
        else:
            self.config["definitions"][name] = schema

        return definition_name

    def _ensure_no_app(self, message):
        """
        Raise an error if the extension was already bound to a Flask app
        :param message: the message of the exception
        """
        if hasattr(self, "app") and self.app is not None:
            raise SwaggerExtensionError(message)
