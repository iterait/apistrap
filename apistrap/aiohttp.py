from __future__ import annotations

import asyncio
import inspect
import json
import logging
import mimetypes
import re
from functools import wraps
from os import path
from pathlib import Path
from typing import Any, Awaitable, Callable, Coroutine, Dict, Generator, List, Optional, Sequence, Tuple, Type, Union

import jinja2
from aiohttp import StreamReader, web
from aiohttp.web_exceptions import HTTPError
from aiohttp.web_request import BaseRequest, Request
from aiohttp.web_response import Response
from aiohttp.web_urldispatcher import AbstractRoute, DynamicResource, PlainResource

from apistrap.errors import ApiClientError, UnsupportedMediaTypeError
from apistrap.extension import Apistrap, ErrorHandler, SecurityScheme
from apistrap.operation_wrapper import OperationWrapper
from apistrap.schemas import ErrorResponse
from apistrap.types import FileResponse
from apistrap.utils import format_exception, resolve_fw_decl

SecurityEnforcer = Callable[[BaseRequest, Sequence[str]], Union[None, Awaitable[None]]]


class AioHTTPOperationWrapper(OperationWrapper):
    def __init__(
        self, extension: AioHTTPApistrap, function: Callable, decorators: Sequence[object], route: AbstractRoute
    ):
        self.route = route
        super().__init__(extension, function, decorators)
        self._extension = extension

    def process_metadata(self):
        super().process_metadata()
        self._get_aiohttp_request_param_name()

    def _get_aiohttp_request_param_name(self) -> Optional[str]:
        """
        Find the parameter into which the AioHTTP request object should be injected.
        """

        param: inspect.Parameter
        result = None
        for param in self._signature.parameters.values():
            if param.annotation == inspect.Parameter.empty:
                continue

            annotation = resolve_fw_decl(self._wrapped_function, param.annotation)
            if issubclass(annotation, BaseRequest):
                if result is not None:
                    raise TypeError("Multiple candidates for request parameter")
                result = param.name

        if result is not None:
            return result

        if "request" in self._signature.parameters.keys():
            if self._signature.parameters["request"].annotation == inspect.Parameter.empty:
                return "request"

        return None

    async def _enforce_security(self, request):
        error = None

        for security_scheme, required_scopes in self._get_required_scopes():
            try:
                # If any enforcer passes without throwing, the user is authenticated
                enforcer = self._extension.security_enforcers[security_scheme]

                if inspect.iscoroutinefunction(enforcer):
                    await enforcer(request, required_scopes)
                else:
                    enforcer(request, required_scopes)
                return
            except Exception as e:
                error = e
        else:
            if error is not None:
                raise error

    def get_decorated_function(self):
        @wraps(self._wrapped_function)
        async def wrapper(request: Request):
            await self._enforce_security(request)

            kwargs = {}

            if self.accepts_body:
                data = await self._load_request_body_primitive(request)
                kwargs.update(self._load_request_body(data))

            for name, param_type in self._path_parameters.items():
                if name in request.match_info.keys():
                    kwargs[name] = param_type(request.match_info[name])

            for name, param_type in self._query_parameters.items():
                if name in request.rel_url.query.keys():
                    kwargs[name] = param_type(request.query[name])
                elif self._signature.parameters[name].default == inspect.Parameter.empty:
                    raise ApiClientError(f"Missing query parameter `{name}`")

            request_param_name = self._get_aiohttp_request_param_name()
            if request_param_name is not None:
                kwargs[request_param_name] = request

            bound = self._signature.bind(**kwargs)

            response, code, mimetype = self._postprocess_response(
                await self._wrapped_function(*bound.args, **bound.kwargs)
            )

            if self.is_raw_response(response):
                if not response.prepared:
                    response.set_status(code)

                return response

            if isinstance(response, FileResponse):
                return await self._stream_file_response(request, response, code, mimetype)

            return web.Response(text=json.dumps(response.to_primitive()), content_type="application/json", status=code)

        return wrapper

    async def _load_request_body_primitive(self, request: BaseRequest) -> dict:
        if request.content_type == "application/json":
            try:
                data = await request.json()
            except json.decoder.JSONDecodeError as ex:
                raise ApiClientError("The request body must be a JSON object") from ex

            if isinstance(data, str):
                raise ApiClientError("The request body must be a JSON object")

            return data
        elif request.content_type in ("application/x-www-form-urlencoded", "multipart/form-data"):
            return await request.post()

        raise UnsupportedMediaTypeError()

    async def _stream_file_response(
        self, request: BaseRequest, response: FileResponse, code: int, mimetype: str = None
    ):
        """
        Stream a file response to the client
        """

        # TODO consider implementing add_etags, cache_timeout and conditional
        headers = {}

        if mimetype:
            headers["Content-Type"] = mimetype
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
            return web.FileResponse(response.filename_or_fp, headers=headers, status=code)
        else:
            # The response contains a file object - stream it to the client
            stream = web.StreamResponse(headers=headers, status=code)

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

    def _get_path_parameters(self) -> Generator[Tuple[str, Type], None, None]:
        if not isinstance(self.route.resource, DynamicResource):
            return

        for name in re.findall(r"{([a-zA-Z0-9]+[^}]*)}", self.route.resource.get_info()["formatter"]):
            param_type = str

            if name not in self._signature.parameters.keys():
                yield name, param_type
                continue

            param_refl: inspect.Parameter = self._signature.parameters[name]

            if param_refl.annotation != inspect.Parameter.empty and param_refl.annotation is not None:
                param_type = resolve_fw_decl(self._wrapped_function, param_refl.annotation)

            if param_type not in (str, int):
                raise TypeError(f"Unsupported path parameter type `{param_type.__name__}`")

            yield name, param_type

    def is_raw_response(self, response: object) -> bool:
        return isinstance(response, Response) or isinstance(response, web.StreamResponse)


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
    def __init__(self):
        super().__init__()
        self.app: web.Application = None
        self.error_middleware = ErrorHandlerMiddleware(self)
        self.security_enforcers: Dict[SecurityScheme, SecurityEnforcer] = {}
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(path.join(path.dirname(__file__), "templates"))
        )
        self._default_error_handlers = [
            ErrorHandler(HTTPError, lambda exc_type: exc_type.status_code, self._handle_http_error),
            ErrorHandler(UnsupportedMediaTypeError, 415, self._handle_client_error),
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

    def add_security_scheme(self, scheme: SecurityScheme, enforcer: SecurityEnforcer, *, default: bool = False):
        """
        Add a security scheme to be used by the API.

        :param scheme: a description of the security scheme
        :param enforcer: a function that checks the requirements of the security scheme
        :param default: should this be used as the default security scheme?
        """

        self._add_security_scheme(scheme, default)
        self.security_enforcers[scheme] = enforcer

    def _handle_server_error(self, exception):
        """
        Default handler for server errors (500-599).

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        logging.exception(exception)
        if asyncio.get_running_loop().get_debug():
            return ErrorResponse(dict(message=str(exception), debug_data=format_exception(exception)))
        else:
            return ErrorResponse(dict(message="Internal server error"))

    def _handle_client_error(self, exception):
        """
        Default handler for client errors (400-499).

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        if asyncio.get_running_loop().get_debug():
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
            raise ValueError()  # pragma: no cover

        logging.exception(exception)
        return ErrorResponse(dict(message=exception.text))

    async def _get_spec(self, request: Request):
        """
        Serves the OpenAPI specification
        """

        return web.Response(text=json.dumps(self.to_openapi_dict()), content_type="application/json", status=200)

    _get_spec.apistrap_ignore = True

    async def _get_ui(self, request: Request):
        """
        Serves Swagger UI
        """

        return web.Response(
            text=self._jinja_env.get_template("apidocs.html").render(apistrap=self),
            content_type="text/html",
            status=200,
        )

    _get_ui.apistrap_ignore = True

    async def _get_redoc(self, request: Request):
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

        operations = [
            AioHTTPOperationWrapper(self, route._handler, self._get_decorators(route._handler), route)
            for route in self.app.router.routes()
            if not self._is_route_ignored(route.method, route._handler)
        ]

        self._extract_specs(operations)

        for op in operations:
            op.route._handler = op.get_decorated_function()

    def _extract_specs(self, operations: List[AioHTTPOperationWrapper]) -> None:
        """
        Extract the specification data from the bound AioHTTP app. If the data was already extracted, do not do
        anything.
        """

        for op in operations:
            url = ""

            if isinstance(op.route.resource, PlainResource):
                url = op.route.resource.get_info()["path"]
            elif isinstance(op.route.resource, DynamicResource):
                url = op.route.resource.get_info()["formatter"]

            self.spec.path(url, {op.route.method.lower(): op.get_openapi_spec()})

    def _is_bound(self) -> bool:
        return self.app is not None

    def _get_default_error_handlers(self) -> Sequence[ErrorHandler]:
        return self._default_error_handlers
