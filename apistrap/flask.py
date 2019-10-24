import inspect
import json
import logging
import re
from functools import wraps
from os import path
from typing import Callable, Dict, Generator, List, Optional, Sequence, Tuple, Type

from flask import Blueprint, Flask, Response, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException

from apistrap.errors import ApiClientError, ApiServerError, UnsupportedMediaTypeError
from apistrap.extension import Apistrap, ErrorHandler, SecurityScheme
from apistrap.operation_wrapper import OperationWrapper
from apistrap.schemas import ErrorResponse
from apistrap.types import FileResponse
from apistrap.utils import format_exception, resolve_fw_decl

SecurityEnforcer = Callable[[Sequence[str]], None]


class FlaskOperationWrapper(OperationWrapper):
    URL_FILTER_MAP = {"string": str, "int": int, "float": float, "path": str}

    def __init__(
        self, extension: Apistrap, function: Callable, decorators: Sequence[object], url_rule: str, method: str
    ):
        self.url_rule = url_rule
        self.method = method
        super().__init__(extension, function, decorators)

    def _enforce_security(self):
        error = None

        for security_scheme, required_scopes in self._get_required_scopes():
            try:
                # If any enforcer passes without throwing, the user is authenticated
                self._extension.security_enforcers[security_scheme](required_scopes)
                return
            except Exception as e:
                error = e
        else:
            if error is not None:
                raise error

    def get_decorated_function(self):
        @wraps(self._wrapped_function)
        def wrapper(*args, **kwargs):
            self._enforce_security()

            if self.accepts_body:
                data = self._load_request_body_primitive()
                kwargs.update(self._load_request_body(data))

            # path parameters are already handled by Flask (and they should be in args/kwargs)

            for name, param_type in self._query_parameters.items():
                if name in request.args.keys():
                    kwargs[name] = param_type(request.args[name])
                elif self._signature.parameters[name].default == inspect.Parameter.empty:
                    raise ApiClientError(f"Missing query parameter `{name}`")

            response, code, mimetype = self._postprocess_response(self._wrapped_function(*args, **kwargs))

            if self.is_raw_response(response):
                return response, code
            if isinstance(response, FileResponse):
                return send_file(
                    filename_or_fp=response.filename_or_fp,
                    mimetype=mimetype or response.mimetype,
                    as_attachment=response.as_attachment,
                    attachment_filename=response.attachment_filename,
                    add_etags=response.add_etags,
                    cache_timeout=response.cache_timeout,
                    conditional=response.conditional,
                    last_modified=response.last_modified,
                )

            response = jsonify(response.to_primitive())
            response.status_code = code
            return response

        return wrapper

    def _load_request_body_primitive(self) -> dict:
        if request.content_type == "application/json":
            try:
                if request.json is None or isinstance(request.json, str):
                    raise ApiClientError("The request body must be a JSON object")
            except json.decoder.JSONDecodeError as ex:
                raise ApiClientError("The request body must be a JSON object") from ex

            return request.json
        elif request.content_type in ("application/x-www-form-urlencoded", "multipart/form-data"):
            return request.form

        raise UnsupportedMediaTypeError()

    def _get_path_parameters(self) -> Generator[Tuple[str, Type], None, None]:
        for param in re.findall("(<([^<>]*:)?([^<>]*)>)", self.url_rule):
            url_filter = param[1].rstrip(":") if param[1] is not None else None
            name = param[2]

            param_type = str

            if url_filter is not None:
                param_type = self.URL_FILTER_MAP.get(url_filter, param_type)

            param_refl: inspect.Parameter = self._signature.parameters[name]

            if param_refl.annotation != inspect.Parameter.empty and param_refl.annotation is not None:
                param_type = resolve_fw_decl(self._wrapped_function, param_refl.annotation)

            yield name, param_type

    def is_raw_response(self, response: object) -> bool:
        return isinstance(response, Response)


class FlaskApistrap(Apistrap):
    def __init__(self):
        super().__init__()
        self._app: Flask = None
        self._specs_extracted = False
        self._operations: Optional[List[FlaskOperationWrapper]] = None
        self.security_enforcers: Dict[SecurityScheme, SecurityEnforcer] = {}

        self._default_error_handlers = (
            ErrorHandler(HTTPException, lambda exc_type: exc_type.code, self.http_error_handler),
            ErrorHandler(UnsupportedMediaTypeError, 415, self.error_handler),
            ErrorHandler(ApiClientError, 400, self.error_handler),
            ErrorHandler(ApiServerError, 500, self.internal_error_handler),
            ErrorHandler(Exception, 500, self.internal_error_handler),
        )

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
        if self.has_error_handlers:
            app.register_error_handler(Exception, self._error_handler)

        app.before_first_request_funcs.append(self._decorate_view_handlers)

    def add_security_scheme(self, scheme: SecurityScheme, enforcer: SecurityEnforcer, *, default: bool = False):
        """
        Add a security scheme to be used by the API.

        :param scheme: a description of the security scheme
        :param enforcer: a function that checks the requirements of the security scheme
        :param default: should this be used as the default security scheme?
        """

        self._add_security_scheme(scheme, default)
        self.security_enforcers[scheme] = enforcer

    def _error_handler(self, exception: Exception):
        response = self.exception_to_response(exception)

        if response is None:
            raise ValueError(f"Unexpected exception type `{type(exception).__name__}`") from exception

        info, code = response

        return jsonify(info.to_primitive()), code

    def _get_default_error_handlers(self) -> Sequence[ErrorHandler]:
        return self._default_error_handlers

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

    def _decorate_view_handlers(self):
        self._extract_operations()

    def _extract_operations(self):
        if self._operations is not None:
            return

        # Gather Flask view functions
        self._operations = []

        for rule in self._app.url_map.iter_rules():
            # Skip Flask's internal static endpoint
            if rule.endpoint == "static":
                continue

            handler = self._app.view_functions[rule.endpoint]

            for method in rule.methods:
                if self._is_route_ignored(method, handler):
                    continue

                op = FlaskOperationWrapper(self, handler, self._get_decorators(handler), str(rule), method)
                self._operations.append(op)
                self._app.view_functions[rule.endpoint] = op.get_decorated_function()

    def _extract_specs(self):
        """
        Extract specification data from the Flask app and save it to the underlying Apispec object
        """
        self._extract_operations()

        for op in self._operations:
            url = str(op.url_rule)
            for arg in re.findall("(<([^<>]*:)?([^<>]*)>)", url):
                url = url.replace(arg[0], "{%s}" % arg[2])

            self.spec.path(url, {op.method.lower(): op.get_openapi_spec()})

        self._specs_extracted = True

    def http_error_handler(self, exception: Exception):
        """
        A handler for Flask HTTPException objects
        :param exception: the exception raised due to a client error
        :return: a response object
        """

        if not isinstance(exception, HTTPException):
            raise ValueError()  # pragma: no cover

        logging.exception(exception)
        return ErrorResponse(dict(message=exception.description))

    def error_handler(self, exception):
        """
        The default handler for API client errors
        :param exception: the exception raised due to a client error
        :return: a response object
        """

        if self._app.debug:
            logging.exception(exception)
            return ErrorResponse(dict(message=str(exception), debug_data=format_exception(exception)))

        return ErrorResponse(dict(message=str(exception)))

    def internal_error_handler(self, exception):
        """
        The default handler for API server errors. It will hide the details when not in debug mode.
        :param exception: the exception raised due to a server error
        :return: a response object
        """

        logging.exception(exception)

        if self._app.debug:
            return ErrorResponse(dict(message=str(exception), debug_data=format_exception(exception)))

        return ErrorResponse(dict(message="Internal server error"))
