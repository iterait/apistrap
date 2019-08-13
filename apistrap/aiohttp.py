import inspect
import json
import logging
import mimetypes
import re
from copy import deepcopy
from itertools import chain
from os import path
from pathlib import Path
from typing import Any, Callable, Coroutine, List, Optional, Tuple, Type, Sequence

import jinja2
from aiohttp import StreamReader, web
from aiohttp.web_exceptions import HTTPError
from aiohttp.web_request import BaseRequest, Request
from aiohttp.web_response import Response
from aiohttp.web_urldispatcher import AbstractRoute, DynamicResource, PlainResource
from schematics import Model
from schematics.exceptions import DataError

from apistrap.decorators import AcceptsDecorator, RespondsWithDecorator
from apistrap.errors import ApiClientError, InvalidResponseError, UnexpectedResponseError
from apistrap.extension import Apistrap, ErrorHandler
from apistrap.schemas import ErrorResponse
from apistrap.types import FileResponse
from apistrap.utils import format_exception, snake_to_camel, get_type_hints


class AioHTTPRespondsWithDecorator(RespondsWithDecorator):
    async def _process_response(self, response, is_last_decorator: bool, *args, **kwargs):
        if isinstance(response, Response) or isinstance(response, web.StreamResponse):
            return response
        if isinstance(response, FileResponse):
            # TODO consider implementing add_etags, cache_timeout and conditional
            headers = {}

            if self._mimetype:
                headers["Content-Type"] = self._mimetype
            elif response.mimetype:
                headers["Content-Type"] = response.mimetype
            elif response.attachment_filename:
                headers["Content-Type"] = mimetypes.guess_type(response.attachment_filename)[0]

            if response.last_modified is not None:
                headers["Last-Modified"] = str(response.last_modified)

            if response.as_attachment:
                if response.attachment_filename is None:
                    raise TypeError("Missing attachment filename")

                headers["Content-Disposition"] = f"attachment,filename={response.attachment_filename}"

            if isinstance(response.filename_or_fp, str) or isinstance(response.filename_or_fp, Path):
                return web.FileResponse(response.filename_or_fp, headers=headers)
            else:
                stream = web.StreamResponse(headers=headers)
                request = next(filter(lambda a: isinstance(a, BaseRequest), chain(args, kwargs.values())), None)

                if request is None:
                    raise TypeError("No request passed to view function")

                await stream.prepare(request)
                buffer_size = 16536

                while True:
                    if isinstance(response.filename_or_fp, StreamReader):
                        chunk = await response.filename_or_fp.read(buffer_size)
                    else:
                        chunk = response.filename_or_fp.read(buffer_size)

                    if not chunk:
                        await stream.write_eof()
                        break

                    await stream.write(chunk)

                return stream

        if not isinstance(response, self._response_class):
            if is_last_decorator:
                raise UnexpectedResponseError(type(response))
            return response  # Let's hope the next RespondsWithDecorator takes care of the response

        try:
            response.validate()
        except DataError as e:
            raise InvalidResponseError(e.errors) from e

        return web.Response(
            text=json.dumps(response.to_primitive()), content_type="application/json", status=self._code
        )


class AioHTTPAcceptsDecorator(AcceptsDecorator):
    def _get_request_content_type(self, request: BaseRequest, *args, **kwargs):
        return request.content_type

    async def _get_request_json(self, request: BaseRequest, *args, **kwargs):
        try:
            data = await request.json()
        except json.decoder.JSONDecodeError as ex:
            raise ApiClientError("The request body must be a JSON object") from ex

        if isinstance(data, str):
            raise ApiClientError("The request body must be a JSON object")

        return data


@web.middleware
class ErrorHandlerMiddleware:
    """
    A configurable handler for exceptions raised when processing HTTP requests.
    """

    def __init__(self, apistrap: "AioHTTPApistrap"):
        """
        :param apistrap: The apistrap extension object
        """
        self._apistrap = apistrap

    def handle_error(self, exception: Exception) -> Tuple[ErrorResponse, int]:
        """
        Find a handler for an exception and invoke it, then return an error response.

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """

        response = self._apistrap.exception_to_response(exception)

        if response is None:
            raise ValueError(f"Unexpected exception type `{type(exception).__name__}`") from exception

        return response

    async def __call__(
        self, request: BaseRequest, handler: Callable[[BaseRequest], Coroutine[Any, Any, Response]]
    ) -> web.Response:
        """
        Invoke the middleware.

        :param request: the API request (will be handled without any modifications)
        :param handler: the handler function (will be invoked without any modifications)
        :return: either the response of the handler or an error message response
        """
        try:
            return await handler(request)
        except Exception as ex:
            error_response, code = self.handle_error(ex)

            return web.Response(
                text=json.dumps(error_response.to_primitive()), content_type="application/json", status=code
            )


class AioHTTPApistrap(Apistrap):
    SYNTHETIC_WRAPPER_ATTR = "aiohttp_apistrap_wrapped_function"

    def __init__(self):
        super().__init__()
        self.app: web.Application = None
        self.error_middleware = ErrorHandlerMiddleware(self)
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(path.join(path.dirname(__file__), "templates"))
        )
        self._default_error_handlers = [
            ErrorHandler(HTTPError, lambda exc_type: exc_type.status_code, self._handle_http_error),
            ErrorHandler(ApiClientError, 400, self._handle_client_error),
            ErrorHandler(Exception, 500, self._handle_server_error),
        ]

    def init_app(self, app: web.Application) -> None:
        """
        Bind the extension to an AioHTTP instance.

        :param app: the AioHTTP instance
        """

        self.app = app
        app.middlewares.append(self.error_middleware)
        app.on_startup.append(self._process_routes)

        if self.spec_url is not None:
            app.router.add_route("get", self.spec_url, self._get_spec)

            if self.ui_url is not None:
                for ui_url in (self.ui_url, self.ui_url + "/"):
                    app.router.add_route("get", ui_url, self._get_ui)

            if self.redoc_url is not None:
                for redoc_url in (self.redoc_url, self.redoc_url + "/"):
                    app.router.add_route("get", redoc_url, self._get_redoc)

    def _handle_server_error(self, exception):
        """
        Default handler for server errors (500-599).

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        logging.exception(exception)
        if self.app.debug:
            return ErrorResponse(dict(message=str(exception), debug_data=format_exception(exception)))
        else:
            return ErrorResponse(dict(message="Internal server error"))

    def _handle_client_error(self, exception):
        """
        Default handler for client errors (400-499).

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        if self.app.debug:
            logging.exception(exception)
            return ErrorResponse(dict(message=str(exception), debug_data=format_exception(exception)))
        else:
            return ErrorResponse(dict(message=str(exception)))

    def _handle_http_error(self, exception: Exception):
        """
        Default handler for http errors (e.g. 404).

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        if not isinstance(exception, HTTPError):
            raise ValueError()

        logging.exception(exception)
        return ErrorResponse(dict(message=exception.text))

    def _get_spec(self, request: Request):
        """
        Serves the OpenAPI specification
        """

        return web.Response(text=json.dumps(self.to_openapi_dict()), content_type="application/json", status=200)

    _get_spec.apistrap_ignore = True

    def _get_ui(self, request: Request):
        """
        Serves Swagger UI
        """

        return web.Response(
            text=self._jinja_env.get_template("apidocs.html").render(apistrap=self),
            content_type="text/html",
            status=200,
        )

    _get_ui.apistrap_ignore = True

    def _get_redoc(self, request: Request):
        """
        Serves ReDoc
        """

        return web.Response(
            text=self._jinja_env.get_template("redoc.html").render(apistrap=self), content_type="text/html", status=200
        )

    _get_redoc.apistrap_ignore = True

    async def _process_routes(self, *args, **kwargs) -> None:
        """
        Process all non-ignored routes and their parameters
        """

        self._extract_specs()

        for route in self.app.router.routes():
            if self._is_route_ignored(route.method, route.handler):
                continue

            self._process_route_parameters(route)

    def _extract_specs(self) -> None:
        """
        Extract the specification data from the bound AioHTTP app. If the data was already extracted, do not do
        anything.
        """

        route: AbstractRoute
        for route in self.app.router.routes():
            if self._is_route_ignored(route.method, route.handler):
                continue

            url = ""

            if isinstance(route.resource, PlainResource):
                url = route.resource.get_info()["path"]
            elif isinstance(route.resource, DynamicResource):
                url = route.resource.get_info()["formatter"]

            self.spec.path(url, {route.method.lower(): self._extract_operation_spec(route)})

    def _check_parameter_type(self, parameter_type: Optional[type]):
        """
        Make sure that given parameter is annotated with a supported type

        :param parameter_type: type of the parameter to check
        :raises TypeError: on unsupported parameters
        """

        if parameter_type not in (str, int, None):
            raise TypeError("Unsupported parameter type")

    def _process_route_parameters(self, route: AbstractRoute) -> None:
        """
        If necessary, wrap the route handler with a coroutine that accepts a AioHTTP request, extracts parameters to
        satisfy the underlying handler and forwards them to the original handler.

        :param route: the route whose handler should be wrapped
        """

        signature = inspect.signature(route.handler)

        request_params = [*filter(lambda hint: issubclass(hint[1], BaseRequest), get_type_hints(route.handler).items())]
        request_param_name: Optional[str] = request_params[0][0] if request_params else None

        if len(request_params) > 1:
            raise TypeError("The decorated view has more than one possible parameter for the AioHTTP request")

        if (
            request_param_name is None
            and "request" in signature.parameters.keys()
            and signature.parameters["request"].annotation == inspect.Signature.empty
        ):
            request_param_name = signature.parameters["request"].name

        takes_aiohttp_request = request_param_name is not None

        additional_params: List[str] = [
            *filter(lambda p: not takes_aiohttp_request or p != request_param_name, signature.parameters.keys())
        ]

        if not takes_aiohttp_request or additional_params:
            handler = route.handler
            accepted_path_params = set(self._get_route_parameter_names(route)).intersection(additional_params)
            type_hints = get_type_hints(route.handler)

            for param in accepted_path_params:
                self._check_parameter_type(type_hints.get(param, None))

            async def wrapped_handler(request: Request):
                kwargs = {
                    name: type_hints[name](request.match_info[name]) if name in type_hints else request.match_info[name]
                    for name in accepted_path_params
                }

                if takes_aiohttp_request:
                    kwargs[request_param_name] = request

                bound_args: inspect.BoundArguments = signature.bind_partial(**kwargs)

                return await handler(*bound_args.args, **bound_args.kwargs)

            setattr(wrapped_handler, self.SYNTHETIC_WRAPPER_ATTR, handler)

            route._handler = wrapped_handler  # HACK

    def _extract_operation_spec(self, route: AbstractRoute) -> dict:
        """
        Extract specification data for a single operation.

        :param route: the route for the operation
        :return: a dict with specification data
        """

        handler = getattr(route.handler, self.SYNTHETIC_WRAPPER_ATTR, route.handler)

        specs_dict = deepcopy(getattr(handler, "specs_dict", {"parameters": [], "responses": {}}))
        specs_dict["operationId"] = snake_to_camel(handler.__name__)

        self._descriptions_from_docblock(handler.__doc__, specs_dict)
        specs_dict["responses"].update(self._error_responses_from_docblock(handler))

        signature = inspect.signature(handler)
        param_doc = self._parameters_from_docblock(handler.__doc__)

        for param_name in self._get_route_parameter_names(route):
            parameter = signature.parameters.get(param_name, None)
            annotation = parameter.annotation if parameter else None

            parameter = {
                "in": "path",
                "name": param_name,
                "required": True,
                "schema": {"type": self._parameter_annotation_to_openapi_type(annotation)},
            }

            if param_name in param_doc.keys():
                parameter["description"] = param_doc[param_name]

            specs_dict["parameters"].append(parameter)

        return specs_dict

    def _get_route_parameter_names(self, route: AbstractRoute) -> List[str]:
        if not isinstance(route.resource, DynamicResource):
            return []

        return re.findall(r"{([a-zA-Z0-9]+[^}]*)}", route.resource.get_info()["formatter"])

    def _is_bound(self) -> bool:
        return self.app is not None

    def _get_default_error_handlers(self) -> Sequence[ErrorHandler]:
        return self._default_error_handlers

    def responds_with(
        self,
        response_class: Type[Model],
        *,
        code: int = 200,
        description: Optional[str] = None,
        mimetype: Optional[str] = None,
    ):
        """
        A decorator that fills in response schemas in the OpenAPI specification. It also converts Schematics models
        returned by view functions to JSON and validates them.
        """
        return AioHTTPRespondsWithDecorator(self, response_class, code=code, description=description, mimetype=mimetype)

    def accepts(self, request_class: Type[Model]):
        """
        A decorator that validates request bodies against a schema and passes it as an argument to the view function.
        The destination argument must be annotated with the request type.
        """
        return AioHTTPAcceptsDecorator(self, request_class)
