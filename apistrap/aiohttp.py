from itertools import chain

import json
import logging
import mimetypes
from aiohttp import web
from aiohttp.web_exceptions import HTTPError
from aiohttp.web_request import BaseRequest
from aiohttp.web_response import Response
from pathlib import Path
from schematics import Model
from schematics.exceptions import DataError
from typing import Type, Optional, Coroutine, Callable, Tuple, Any

from apistrap import Swagger
from apistrap.decorators import RespondsWithDecorator, AcceptsDecorator
from apistrap.errors import UnexpectedResponseError, InvalidResponseError, ApiClientError
from apistrap.schemas import ErrorResponse
from apistrap.types import FileResponse
from apistrap.utils import format_exception


class AioHTTPRespondsWithDecorator(RespondsWithDecorator):
    async def _process_response(self, response, is_last_decorator: bool, *args, **kwargs):
        if isinstance(response, Response) or isinstance(response, web.StreamResponse):
            return response
        if isinstance(response, FileResponse):
            # TODO consider implementing add_etags, cache_timeout and conditional
            headers = {}

            if self._mimetype:
                headers['Content-Type'] = self._mimetype
            elif response.mimetype:
                headers['Content-Type'] = response.mimetype
            elif response.attachment_filename:
                headers['Content-Type'] = mimetypes.guess_type(response.attachment_filename)[0]

            if response.last_modified is not None:
                headers['Last-Modified'] = str(response.last_modified)

            if response.as_attachment:
                if response.attachment_filename is None:
                    raise TypeError('Missing attachment filename')

                headers['Content-Disposition'] = f'attachment,filename={response.attachment_filename}'

            if isinstance(response.filename_or_fp, str) or isinstance(response.filename_or_fp, Path):
                return web.FileResponse(response.filename_or_fp, headers=headers)
            else:
                stream = web.StreamResponse(headers=headers)
                request = next(filter(lambda a: isinstance(a, BaseRequest), chain(args, kwargs.values())), None)

                if request is None:
                    raise TypeError('No request passed to view function')

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

        return web.Response(text=json.dumps(response.to_primitive()), content_type="application/json",
                            status=self._code)


class AioHTTPAcceptsDecorator(AcceptsDecorator):
    def _get_request_content_type(self, request: BaseRequest, *args, **kwargs):
        return request.content_type

    async def _get_request_json(self, request: BaseRequest, *args, **kwargs):
        return await request.json()


ErrorHandler = Callable[[Exception], Tuple[ErrorResponse, int]]


@web.middleware
class ErrorHandlerMiddleware:
    """
    A configurable handler for exceptions raised when processing HTTP requests.
    """

    def __init__(self, apistrap: 'AioHTTPApistrap'):
        """
        :param apistrap: The apistrap extension object
        """
        self._apistrap = apistrap
        self._handlers = []
        self._default_handlers = [
            (HTTPError, self._handle_http_error),
            (ApiClientError, self._handle_client_error),
            (Exception, self._handle_server_error)
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
                self._handlers,
                self._default_handlers if self._apistrap.use_default_error_handlers else []
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
            return ErrorResponse(dict(
                message=str(exception),
                debug_data=format_exception(exception)
            )), 500
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
            return ErrorResponse(dict(
                message=str(exception),
                debug_data=format_exception(exception)
            )), 400
        else:
            return ErrorResponse(dict(message=str(exception))), 400

    def _handle_http_error(self, exception):
        """
        Default handler for http errors (e.g. 404).

        :param exception: the exception to be handled
        :return: an ErrorResponse instance
        """
        logging.exception(exception)
        return ErrorResponse(dict(
            message=exception.text
        )), exception.status_code

    async def __call__(self, request: BaseRequest,
                       handler: Callable[[BaseRequest], Coroutine[Any, Any, Response]]) -> web.Response:
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
                text=json.dumps(error_response.to_primitive()),
                content_type="application/json",
                status=code
            )


class AioHTTPApistrap(Swagger):
    def __init__(self):
        super().__init__()
        self.app: web.Application = None
        self.error_middleware = ErrorHandlerMiddleware(self)

    def init_app(self, app: web.Application):
        self.app = app
        app.middlewares.append(self.error_middleware)

    def responds_with(self, response_class: Type[Model], *, code: int=200, description: Optional[str]=None,
                      mimetype: Optional[str]=None):
        """
        A decorator that fills in response schemas in the Swagger specification. It also converts Schematics models
        returned by view functions to JSON and validates them.
        """
        return AioHTTPRespondsWithDecorator(self, response_class, code=code, description=description, mimetype=mimetype)

    def accepts(self, request_class: Type[Model]):
        """
        A decorator that validates request bodies against a schema and passes it as an argument to the view function.
        The destination argument must be annotated with the request type.
        """
        return AioHTTPAcceptsDecorator(self, request_class)
