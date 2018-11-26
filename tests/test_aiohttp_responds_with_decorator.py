import contextlib
import pytest
from aiohttp import web
from schematics import Model
from schematics.types import StringType, IntType
from unittest import mock

from apistrap.aiohttp import ErrorHandlerMiddleware
from apistrap.errors import UnexpectedResponseError, InvalidResponseError


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
def app_with_responds_with(aiohttp_apistrap):
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

    app.add_routes(routes)
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


async def test_accepts(app_with_responds_with, aiohttp_client):
    client = await aiohttp_client(app_with_responds_with)
    response = await client.get('/')

    assert response.status == 200

    data = await response.json()
    assert data['string_field'] == 'Hello World'


async def test_error(app_with_responds_with, aiohttp_client):
    client = await aiohttp_client(app_with_responds_with)
    response = await client.get('/error')

    assert response.status == 400

    data = await response.json()
    assert data['error_message'] == 'Error'


async def test_weird(app_with_responds_with, aiohttp_client):
    client = await aiohttp_client(app_with_responds_with)

    with aiohttp_catch_exceptions(app_with_responds_with) as holder:
        await client.get('/weird')
        assert holder.exc is not None
        assert isinstance(holder.exc, UnexpectedResponseError)


async def test_invalid(app_with_responds_with, aiohttp_client):
    client = await aiohttp_client(app_with_responds_with)
    with aiohttp_catch_exceptions(app_with_responds_with) as holder:
        await client.get('/invalid')
        assert holder.exc is not None
        assert isinstance(holder.exc, InvalidResponseError)


# TODO test file response once it's finished
