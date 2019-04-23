import inspect
import json
import logging
import re
from copy import deepcopy
from os import path
from typing import Optional, Type

from flask import Blueprint, Flask, Response, jsonify, render_template, request, send_file
from schematics import Model
from schematics.exceptions import DataError
from werkzeug.exceptions import HTTPException

from apistrap.decorators import AcceptsDecorator, RespondsWithDecorator
from apistrap.errors import ApiClientError, ApiServerError, InvalidResponseError, UnexpectedResponseError
from apistrap.extension import Apistrap
from apistrap.schemas import ErrorResponse
from apistrap.types import FileResponse
from apistrap.utils import format_exception, snake_to_camel


class FlaskRespondsWithDecorator(RespondsWithDecorator):
    def _process_response(self, response, is_last_decorator: bool, *args, **kwargs):
        if isinstance(response, Response):
            return response
        if isinstance(response, FileResponse):
            return send_file(
                filename_or_fp=response.filename_or_fp,
                mimetype=self._mimetype or response.mimetype,
                as_attachment=response.as_attachment,
                attachment_filename=response.attachment_filename,
                add_etags=response.add_etags,
                cache_timeout=response.cache_timeout,
                conditional=response.conditional,
                last_modified=response.last_modified,
            )
        if not isinstance(response, self._response_class):
            if is_last_decorator:
                raise UnexpectedResponseError(type(response))
            return response  # Let's hope the next RespondsWithDecorator takes care of the response

        try:
            response.validate()
        except DataError as ex:
            raise InvalidResponseError(ex.errors) from ex

        response = jsonify(response.to_primitive())
        response.status_code = self._code
        return response


class FlaskAcceptsDecorator(AcceptsDecorator):
    def _get_request_content_type(self, *args, **kwargs):
        return request.content_type

    def _get_request_json(self, *args, **kwargs):
        try:
            if request.json is None or isinstance(request.json, str):
                raise ApiClientError("The request body must be a JSON object")
        except json.decoder.JSONDecodeError as ex:
            raise ApiClientError("The request body must be a JSON object") from ex

        return request.json


class FlaskApistrap(Apistrap):
    def __init__(self):
        super().__init__()
        self._app: Flask = None
        self._specs_extracted = False

    def init_app(self, app: Flask):
        """
        Bind the extension to a Flask instance.

        :param app: the Flask instance
        """
        self._app = app
        blueprint = Blueprint("apistrap", __name__, template_folder=path.join(path.dirname(__file__), "templates"))

        if self.spec_url is not None:
            blueprint.route(self.spec_url, methods=["GET"])(self._get_spec)

        if self.spec_url is not None and self.ui_url is not None:
            blueprint.route(self.ui_url)(self._get_ui)
            blueprint.route(self.ui_url + "/")(self._get_ui)

        if self.spec_url is not None and self.redoc_url is not None:
            blueprint.route(self.redoc_url)(self._get_redoc)
            blueprint.route(self.redoc_url + "/")(self._get_redoc)

        app.register_blueprint(blueprint)

        if self.use_default_error_handlers:
            app.register_error_handler(HTTPException, self.http_error_handler)
            app.register_error_handler(ApiClientError, self.error_handler)
            app.register_error_handler(ApiServerError, self.internal_error_handler)
            app.register_error_handler(Exception, self.internal_error_handler)

    def _is_bound(self) -> bool:
        return self._app is not None

    def _get_spec(self):
        """
        Serves the OpenAPI specification
        """
        self._extract_specs()
        return jsonify(self.to_openapi_dict())

    _get_spec.apistrap_ignore = True

    def _get_ui(self):
        """
        Serves Swagger UI
        """
        return render_template("apidocs.html", apistrap=self)

    _get_ui.apistrap_ignore = True

    def _get_redoc(self):
        """
        Serves ReDoc
        """
        return render_template("redoc.html", apistrap=self)

    _get_redoc.apistrap_ignore = True

    def _extract_specs(self):
        """
        Extract specification data from the Flask app and save it to the underlying Apispec object
        """
        if self._specs_extracted:
            return

        for rule in self._app.url_map.iter_rules():
            # Skip Flask's internal static endpoint
            if rule.endpoint == "static":
                continue

            handler = self._app.view_functions[rule.endpoint]

            url = str(rule)
            for arg in re.findall("(<([^<>]*:)?([^<>]*)>)", url):
                url = url.replace(arg[0], "{%s}" % arg[2])

            for method in rule.methods:
                if self._is_route_ignored(method, handler):
                    continue

                self.spec.path(url, {method.lower(): self._extract_operation_specs(handler)})

        self._specs_extracted = True

    def _extract_operation_specs(self, handler):
        """
        Extract operation specification data from a Flask view handler

        :param handler: the Flask handler to extract
        :return: a dictionary containing the specification data
        """

        specs_dict = deepcopy(getattr(handler, "specs_dict", {"parameters": [], "responses": {}}))
        specs_dict["summary"] = self._summary_from_docblock(handler.__doc__)
        specs_dict["operationId"] = snake_to_camel(handler.__name__)

        signature = inspect.signature(handler)
        ignored = getattr(handler, "_ignored_params", [])
        param_doc = self._parameters_from_docblock(handler.__doc__)

        for arg in signature.parameters.values():
            if arg.name not in ignored:
                param_data = {
                    "in": "path",
                    "name": arg.name,
                    "required": True,
                    "schema": {"type": self._parameter_annotation_to_openapi_type(arg.annotation)},
                }

                if arg.name in param_doc.keys():
                    param_data["description"] = param_doc[arg.name]

                specs_dict["parameters"].append(param_data)

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
            error_response = ErrorResponse(dict(message=str(exception), debug_data=format_exception(exception)))
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
            error_response = ErrorResponse(dict(message=str(exception), debug_data=format_exception(exception)))
        else:
            error_response = ErrorResponse(dict(message="Internal server error"))

        return jsonify(error_response.to_primitive()), 500

    def responds_with(
        self,
        response_class: Type[Model],
        *,
        code: int = 200,
        description: Optional[str] = None,
        mimetype: Optional[str] = None
    ):
        return FlaskRespondsWithDecorator(self, response_class, code=code, description=description, mimetype=mimetype)

    def accepts(self, request_class: Type[Model]):
        return FlaskAcceptsDecorator(self, request_class)
