import json
import logging
import mimetypes
import re
from copy import deepcopy
from itertools import chain
from os import path
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, Tuple, Type

import jinja2
from aiohttp import web
from aiohttp.web_exceptions import HTTPError
from aiohttp.web_request import BaseRequest, Request
from aiohttp.web_response import Response
from aiohttp.web_urldispatcher import AbstractRoute, DynamicResource, PlainResource
from schematics import Model
from schematics.exceptions import DataError

from apistrap.decorators import AcceptsDecorator, RespondsWithDecorator
from apistrap.errors import ApiClientError, InvalidResponseError, UnexpectedResponseError
from apistrap.extension import Apistrap
from apistrap.schemas import ErrorResponse
from apistrap.types import FileResponse
from apistrap.utils import format_exception, snake_to_camel


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

                while True:
                    chunk = response.filename_or_fp.read(16536)
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


ErrorHandler = Callable[[Exception], Tuple[ErrorResponse, int]]


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
        self._handlers = []
        self._default_handlers = [
            (HTTPError, self._handle_http_error),
            (ApiClientError, self._handle_client_error),
            (Exception, self._handle_server_error),
        ]

    def add_handler(self, exception_type: Type[Exception], handler: ErrorHandler) -> None:
        """
        Add a new error handler.

        :param exception_type: Only instances of this exception type will be handled by the handler
        :param handler: A function that handles the exception and returns a response
        """
        self._handlers.append((exception_type, handler))

    def handle_error(self, exception: Exception) -> Tuple[ErrorResponse, int]:
        """
        Find a handler for an exception and invoke it, then return an error response.

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        for handled_type, handler in chain(
            self._handlers, self._default_handlers if self._apistrap.use_default_error_handlers else []
        ):
            if isinstance(exception, handled_type):
                return handler(exception)

        raise ValueError(f"Unexpected exception type `{type(exception).__name__}`") from exception

    def _handle_server_error(self, exception):
        """
        Default handler for server errors (500-599).

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        logging.exception(exception)
        if self._apistrap.app.debug:
            return ErrorResponse(dict(message=str(exception), debug_data=format_exception(exception))), 500
        else:
            return ErrorResponse(dict(message="Internal server error")), 500

    def _handle_client_error(self, exception):
        """
        Default handler for client errors (400-499).

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        if self._apistrap.app.debug:
            logging.exception(exception)
            return ErrorResponse(dict(message=str(exception), debug_data=format_exception(exception))), 400
        else:
            return ErrorResponse(dict(message=str(exception))), 400

    def _handle_http_error(self, exception):
        """
        Default handler for http errors (e.g. 404).

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        logging.exception(exception)
        return ErrorResponse(dict(message=exception.text)), exception.status_code

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
    def __init__(self):
        super().__init__()
        self.app: web.Application = None
        self.error_middleware = ErrorHandlerMiddleware(self)
        self._specs_extracted = False
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(path.join(path.dirname(__file__), "templates"))
        )

    def init_app(self, app: web.Application) -> None:
        """
        Bind the extension to an AioHTTP instance.

        :param app: the AioHTTP instance
        """

        self.app = app
        app.middlewares.append(self.error_middleware)

        if self.spec_url is not None:
            app.router.add_route("get", self.spec_url, self._get_spec)

            if self.ui_url is not None:
                for ui_url in (self.ui_url, self.ui_url + "/"):
                    app.router.add_route("get", ui_url, self._get_ui)

    def _get_spec(self, request: Request):
        """
        Serves the OpenAPI specification
        """

        self._extract_specs()
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

    def _extract_specs(self) -> None:
        """
        Extract the specification data from the bound AioHTTP app. If the data was already extracted, do not do
        anything.
        """

        if self._specs_extracted:
            return

        route: AbstractRoute
        for route in self.app.router.routes():
            if getattr(route.handler, "apistrap_ignore", False):
                continue

            if route.method.lower() not in ["get", "post", "put", "delete", "patch"]:
                continue

            url = ""

            if isinstance(route.resource, PlainResource):
                url = route.resource.get_info()["path"]
            elif isinstance(route.resource, DynamicResource):
                url = route.resource.get_info()["formatter"]

            self.spec.path(url, {route.method.lower(): self._extract_operation_spec(route)})

        self._specs_extracted = True

    def _extract_operation_spec(self, route: AbstractRoute) -> dict:
        """
        Extract specification data for a single operation.

        :param route: the route for the operation
        :return: a dict with specification data
        """

        specs_dict = deepcopy(getattr(route.handler, "specs_dict", {"parameters": [], "responses": {}}))
        specs_dict["summary"] = route.handler.__doc__.strip() if route.handler.__doc__ else ""

        if isinstance(route.resource, DynamicResource):
            parameters = re.findall(r"{([a-zA-Z0-9]+[^}]*)}", route.resource.get_info()["formatter"])

            for arg in parameters:
                param_data = {
                    "in": "path",
                    "name": arg,
                    "required": True,
                    "schema": {"type": "string"},  # TODO support other types too
                }

                specs_dict["parameters"].append(param_data)

        specs_dict["operationId"] = snake_to_camel(route.handler.__name__)

        return specs_dict

    def _is_bound(self) -> bool:
        return self.app is not None

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
