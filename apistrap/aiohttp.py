import json
from aiohttp import web
from aiohttp.web_request import BaseRequest
from aiohttp.web_response import Response
from schematics import Model
from schematics.exceptions import DataError
from typing import Type, Optional

from apistrap import Swagger
from apistrap.decorators import RespondsWithDecorator, AcceptsDecorator
from apistrap.errors import UnexpectedResponseError, InvalidResponseError
from apistrap.types import FileResponse


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


class AioHTTPApistrap(Swagger):
    def init_app(self, app: web.Application):
        pass

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
