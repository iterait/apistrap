import inspect
from copy import deepcopy
from os import path

import logging
import re
from typing import Type, Optional

from flask import Flask, jsonify, Blueprint, render_template
from schematics import Model
from werkzeug.exceptions import HTTPException

from apistrap.decorators import RespondsWithDecorator, AcceptsDecorator
from apistrap.errors import ApiClientError, ApiServerError
from apistrap.extension import Apistrap
from apistrap.schemas import ErrorResponse
from apistrap.utils import format_exception, snake_to_camel


class FlaskApistrap(Apistrap):
    PARAMETER_TYPE_MAP = {
        int: "integer",
        str: "string"
    }

    def __init__(self):
        super().__init__()
        self._app: Flask = None
        self._specs_extracted = False

    def init_app(self, app: Flask):
        self._app = app
        blueprint = Blueprint("apistrap", __name__, template_folder=path.join(path.dirname(__file__), "templates"))

        if self.spec_url is not None:
            blueprint.route(self.spec_url, methods=["GET"])(self._get_spec)

        if self.spec_url is not None and self.ui_url is not None:
            blueprint.route(self.ui_url)(self._get_ui)
            blueprint.route(self.ui_url + "/")(self._get_ui)

        app.register_blueprint(blueprint)

        if self.use_default_error_handlers:
            app.register_error_handler(HTTPException, self.http_error_handler)
            app.register_error_handler(ApiClientError, self.error_handler)
            app.register_error_handler(ApiServerError, self.internal_error_handler)
            app.register_error_handler(Exception, self.internal_error_handler)

    def _is_bound(self) -> bool:
        return self._app is not None

    def _get_spec(self):
        self._extract_specs()
        return jsonify(self.to_dict())

    def _get_ui(self):
        return render_template("apidocs.html", apistrap=self)

    def _extract_specs(self):
        if self._specs_extracted:
            return

        for rule in self._app.url_map.iter_rules():
            blueprint_name = rule.endpoint.split(".")[0] if "." in rule.endpoint else None

            # Skip endpoints added by apistrap
            if blueprint_name == "apistrap":
                continue

            # Skip Flask's internal static endpoint
            if rule.endpoint == "static":
                continue

            handler = self._app.view_functions[rule.endpoint]

            url = str(rule)
            for arg in re.findall('(<([^<>]*:)?([^<>]*)>)', url):
                url = url.replace(arg[0], '{%s}' % arg[2])

            for method in rule.methods:
                if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                    continue

                self.spec.path(url, {
                    method.lower(): self._extract_operation_specs(handler)
                })

        self._specs_extracted = True

    def _extract_operation_specs(self, handler):
        specs_dict = deepcopy(getattr(handler, "specs_dict", {
            "parameters": [],
            "responses": {}
        }))
        specs_dict["summary"] = handler.__doc__

        signature = inspect.signature(handler)
        ignored = getattr(handler, "_ignored_params", [])

        for arg in signature.parameters.values():
            if arg.name not in ignored:
                param_data = {
                    "in": "path",
                    "name": arg.name,
                    "required": True,
                    "schema": {
                        "type": self.PARAMETER_TYPE_MAP.get(arg.annotation, "string")
                    }
                }

                specs_dict["parameters"].append(param_data)

        specs_dict["operationId"] = snake_to_camel(handler.__name__)

        return specs_dict

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

        if self._app.debug:
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

        if self._app.debug:
            error_response = ErrorResponse(dict(
                message=str(exception),
                debug_data=format_exception(exception)
            ))
        else:
            error_response = ErrorResponse(dict(message="Internal server error"))

        return jsonify(error_response.to_primitive()), 500

    def responds_with(self, response_class: Type[Model], *, code: int = 200, description: Optional[str] = None,
                      mimetype: Optional[str] = None):
        return RespondsWithDecorator(self, response_class, code=code, description=description, mimetype=mimetype)

    def accepts(self, request_class: Type[Model]):
        return AcceptsDecorator(self, request_class)
