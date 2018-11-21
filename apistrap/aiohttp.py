import json
import logging
from aiohttp import web
from aiohttp.web_exceptions import HTTPError
from aiohttp.web_request import BaseRequest
from aiohttp.web_response import Response
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
    def _process_response(self, response, is_last_decorator: bool):
        if isinstance(response, Response):
            return response
        if isinstance(response, FileResponse):
            return web.FileResponse(response.filename_or_fp)  # TODO
        if not isinstance(response, self._response_class):
            if is_last_decorator:
                raise UnexpectedResponseError(type(response))
            return response  # Let's hope the next RespondsWithDecorator takes care of the response

        try:
            response.validate()
        except DataError as e:
            raise InvalidResponseError(e.errors) from e

        return web.Response(text=json.dumps(response.to_primitive()), content_type="application/json", status=self._code)


class AioHTTPAcceptsDecorator(AcceptsDecorator):
    def _get_request_content_type(self, request: BaseRequest, *args, **kwargs):
        return request.content_type

    async def _get_request_json(self, request: BaseRequest, *args, **kwargs):
        return await request.json()


@web.middleware
class ErrorHandlerMiddleware:
    def __init__(self, debug: bool):
        self.debug = debug

    def handle_error(self, exception: Exception) -> Tuple[ErrorResponse, int]:
        if isinstance(exception, HTTPError):
            logging.exception(exception)
            return ErrorResponse(dict(
                message=exception.text
            )), exception.status_code
        elif isinstance(exception, ApiClientError):
            if self.debug:
                logging.exception(exception)
                return ErrorResponse(dict(
                    message=str(exception),
                    debug_data=format_exception(exception)
                )), 400
            else:
                return ErrorResponse(dict(message=str(exception))), 400
        else:
            logging.exception(exception)

            if self.debug:
                return ErrorResponse(dict(
                    message=str(exception),
                    debug_data=format_exception(exception)
                )), 500
            else:
                return ErrorResponse(dict(message="Internal server error")), 500

    async def __call__(self, request: BaseRequest, handler: Callable[[BaseRequest], Coroutine[Any, Any, Response]]) -> web.Response:
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
    def init_app(self, app: web.Application):
        if self.use_default_error_handlers:
            app.middlewares.append(ErrorHandlerMiddleware(app.debug))

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
