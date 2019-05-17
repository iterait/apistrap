import contextlib
import io
import json
import re
from unittest import mock

import pytest
from aiohttp import ClientSession, web
from aiohttp.web_request import Request
from schematics import Model
from schematics.types import IntType, StringType

from apistrap.aiohttp import ErrorHandlerMiddleware
from apistrap.errors import InvalidResponseError, UnexpectedResponseError
from apistrap.types import FileResponse


class OkResponse(Model):
    string_field = StringType(required=True)


class ErrorResponse(Model):
    error_message = StringType(required=True)


class WeirdResponse(Model):
    string_field = StringType(required=True)


class RequestModel(Model):
    string_field: str = StringType(required=True)
    int_field: int = IntType(required=True)


@pytest.fixture()
def app_with_responds_with(aiohttp_apistrap, tmpdir):
    app = web.Application()
    routes = web.RouteTableDef()

    @routes.get('/')
    @aiohttp_apistrap.responds_with(OkResponse)
    @aiohttp_apistrap.responds_with(ErrorResponse, code=400)
    async def view(request):
        return OkResponse(dict(string_field='Hello World'))

    @routes.get('/error')
    @aiohttp_apistrap.responds_with(OkResponse)
    @aiohttp_apistrap.responds_with(ErrorResponse, code=400)
    async def error(request):
        return ErrorResponse(dict(error_message='Error'))

    @routes.get('/weird')
    @aiohttp_apistrap.responds_with(OkResponse)
    @aiohttp_apistrap.responds_with(ErrorResponse, code=400)
    async def weird(request):
        return WeirdResponse(dict(string_field='Hello Weird World'))

    @routes.get('/invalid')
    @aiohttp_apistrap.responds_with(OkResponse)
    @aiohttp_apistrap.responds_with(ErrorResponse, code=400)
    async def invalid(request):
        return OkResponse(dict())

    @routes.get("/file")
    @aiohttp_apistrap.responds_with(FileResponse)
    async def get_file(request):
        message = 'hello'
        return FileResponse(filename_or_fp=io.BytesIO(message.encode('UTF-8')),
                            as_attachment=True,
                            attachment_filename='hello.txt')

    @routes.get("/file_by_path")
    @aiohttp_apistrap.responds_with(FileResponse)
    async def get_file_by_path(request):
        path = tmpdir.join("file.txt")
        path.write(b'hello')

        return FileResponse(filename_or_fp=str(path),
                            as_attachment=True,
                            attachment_filename='hello.txt')

    @routes.get('/file_without_name')
    @aiohttp_apistrap.responds_with(FileResponse)
    async def get_file_without_name(request):
        message = 'hello'
        return FileResponse(filename_or_fp=io.BytesIO(message.encode('UTF-8')),
                            as_attachment=True)

    @routes.get('/file_with_mimetype')
    @aiohttp_apistrap.responds_with(FileResponse)
    async def get_file_with_mimetype(request):
        message = '<a href="www.hello.com"></a>'
        return FileResponse(filename_or_fp=io.BytesIO(message.encode('UTF-8')),
                            as_attachment=True,
                            attachment_filename='hello.html',
                            mimetype='text/html')

    @routes.get('/file_with_mimetype_decorator')
    @aiohttp_apistrap.responds_with(FileResponse, mimetype='text/html')
    async def get_file_with_mimetype(request):
        message = '<a href="www.hello.com"></a>'
        return FileResponse(filename_or_fp=io.BytesIO(message.encode('UTF-8')),
                            as_attachment=True,
                            attachment_filename='hello.html',
                            mimetype='text/plain')

    @routes.get("/file_timestamp")
    @aiohttp_apistrap.responds_with(FileResponse)
    async def get_file(request):
        message = 'hello'
        return FileResponse(filename_or_fp=io.BytesIO(message.encode('UTF-8')),
                            as_attachment=True,
                            attachment_filename='hello.txt',
                            last_modified=2018)

    @routes.get("/file_stream")
    @aiohttp_apistrap.responds_with(FileResponse)
    async def get_stream_file(request: Request):
        session = ClientSession()

        response = await session.get("https://api.ipify.org")
        return FileResponse(filename_or_fp=response.content)

    app.add_routes(routes)
    aiohttp_apistrap.use_default_error_handlers = False
    aiohttp_apistrap.init_app(app)
    yield app


@contextlib.contextmanager
def aiohttp_catch_exceptions(app: web.Application):
    class ExceptionHolder:
        def __init__(self):
            self.exc = None

        def hold(self, ex):
            self.exc = ex

    holder = ExceptionHolder()

    middleware = next(filter(lambda m: isinstance(m, ErrorHandlerMiddleware), app.middlewares), None)
    if middleware is None:
        raise ValueError('No middleware to patch')

    with mock.patch.object(middleware, 'handle_error', holder.hold):
        yield holder


async def test_accepts(app_with_responds_with, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_responds_with)
    response = await client.get('/')

    assert response.status == 200

    data = await response.json()
    assert data['string_field'] == 'Hello World'


async def test_error(app_with_responds_with, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_responds_with)
    response = await client.get('/error')

    assert response.status == 400

    data = await response.json()
    assert data['error_message'] == 'Error'


async def test_weird(app_with_responds_with, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_responds_with)

    with aiohttp_catch_exceptions(app_with_responds_with) as holder:
        await client.get('/weird')
        assert holder.exc is not None
        assert isinstance(holder.exc, UnexpectedResponseError)


async def test_invalid(app_with_responds_with, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_responds_with)

    with aiohttp_catch_exceptions(app_with_responds_with) as holder:
        await client.get('/invalid')
        assert holder.exc is not None
        assert isinstance(holder.exc, InvalidResponseError)


@pytest.mark.parametrize('endpoint', ['/file', '/file_by_path'])
async def test_file_response(aiohttp_initialized_client, app_with_responds_with, endpoint):
    client = await aiohttp_initialized_client(app_with_responds_with)
    response = await client.get(endpoint)
    assert await response.read() == b'hello'


async def test_file_response_error(app_with_responds_with, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_responds_with)

    with aiohttp_catch_exceptions(app_with_responds_with) as holder:
        await client.get('/file_without_name')
        assert holder.exc is not None
        assert isinstance(holder.exc, TypeError)


@pytest.mark.parametrize('endpoint', ['/file_with_mimetype', '/file_with_mimetype_decorator'])
async def test_file_response_mimetype(aiohttp_initialized_client, app_with_responds_with, endpoint):
    client = await aiohttp_initialized_client(app_with_responds_with)
    response = await client.get(endpoint)
    assert await response.read() == b'<a href="www.hello.com"></a>'
    assert response.headers['Content-Type'] == 'text/html'


async def test_file_response_timestamp(aiohttp_initialized_client, app_with_responds_with):
    client = await aiohttp_initialized_client(app_with_responds_with)
    response = await client.get('/file_timestamp')
    assert await response.read() == b'hello'
    assert response.headers['Last-Modified'] == '2018'


async def test_file_stream(aiohttp_initialized_client, app_with_responds_with):
    client = await aiohttp_initialized_client(app_with_responds_with)
    response = await client.get('/file_stream')

    data = await response.read()
    assert re.match(r"^\d+\.\d+\.\d+\.\d+", data.decode()) is not None
