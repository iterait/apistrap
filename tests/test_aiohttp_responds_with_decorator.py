import pytest
from aiohttp import web
from schematics import Model
from schematics.types import StringType, IntType


class OkResponse(Model):
    string_field = StringType(required=True)


class ErrorResponse(Model):
    error_message = StringType(required=True)


class RequestModel(Model):
    string_field: str = StringType(required=True)
    int_field: int = IntType(required=True)


@pytest.fixture()
def app_with_responds_with(aiohttp_apistrap):
    app = web.Application()
    routes = web.RouteTableDef()

    @routes.get("/")
    @aiohttp_apistrap.responds_with(OkResponse)
    async def view(request):
        return OkResponse(dict(string_field="Hello World"))

    @routes.get("/error")
    @aiohttp_apistrap.responds_with(ErrorResponse, code=400)
    async def error(request):
        return ErrorResponse(dict(error_message="Error"))

    app.add_routes(routes)
    yield app


async def test_accepts(app_with_responds_with, aiohttp_client):
    client = await aiohttp_client(app_with_responds_with)
    response = await client.get("/")

    assert response.status == 200

    data = await response.json()
    assert data["string_field"] == "Hello World"


async def test_error(app_with_responds_with, aiohttp_client):
    client = await aiohttp_client(app_with_responds_with)
    response = await client.get("/error")

    assert response.status == 400

    data = await response.json()
    assert data["error_message"] == "Error"
