import json

import pytest
from aiohttp import web

from apistrap.aiohttp import AioHTTPApistrap


@pytest.fixture(scope="function")
def app_with_qs_params():
    routes = web.RouteTableDef()
    oapi = AioHTTPApistrap()

    @routes.get("/")
    @oapi.accepts_qs("param_a", "param_b")
    async def view(param_a: str, param_b: int = 999):
        """
        A cool view handler.
        :param param_a: Parameter A
        :param param_b: Parameter B
        """

        return web.Response(content_type="application/json", text=json.dumps({"a": param_a, "b": param_b}))

    app = web.Application()
    app.add_routes(routes)
    oapi.init_app(app)

    yield app


async def test_flask_query_string_spec(app_with_qs_params, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_qs_params)
    response = await client.get("/spec.json")

    assert response.status == 200
    json = await response.json()

    params = json["paths"]["/"]["get"]["parameters"]
    params.sort(key=lambda p: p["name"])

    assert len(params) == 2
    assert params[0] == {
        "name": "param_a",
        "in": "query",
        "description": "Parameter A",
        "required": True,
        "schema": {"type": "string"},
    }

    assert params[1] == {
        "name": "param_b",
        "in": "query",
        "description": "Parameter B",
        "required": False,
        "schema": {"type": "integer"},
    }


async def test_flask_query_string_passing(app_with_qs_params, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_qs_params)
    response = await client.get("/?param_a=hello&param_b=42")

    assert response.status == 200
    json = await response.json()

    assert json["a"] == "hello"
    assert json["b"] == 42


async def test_flask_query_string_optional_params(app_with_qs_params, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_qs_params)
    response = await client.get("/?param_a=hello")

    assert response.status == 200
    json = await response.json()

    assert json["a"] == "hello"
    assert json["b"] == 999
