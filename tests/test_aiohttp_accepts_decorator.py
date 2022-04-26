import json

import pytest
from aiohttp import web
from aiohttp.web_request import BaseRequest, Request
from pydantic import BaseModel


class RequestModel(BaseModel):
    string_field: str
    int_field: int


@pytest.fixture()
def app_with_accepts(aiohttp_apistrap):
    app = web.Application()
    routes = web.RouteTableDef()

    @routes.post("/")
    @aiohttp_apistrap.accepts(RequestModel)
    async def view(aiohttp_request: Request, req: RequestModel):
        assert isinstance(aiohttp_request, BaseRequest)
        assert req.string_field == "foo"
        assert req.int_field == 42
        return web.Response(content_type="application/json", text=json.dumps({"status": "OK"}))

    app.add_routes(routes)
    aiohttp_apistrap.init_app(app)
    yield app


async def test_accepts(app_with_accepts, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_accepts)
    response = await client.post(
        "/", headers={"content-type": "application/json"}, data=json.dumps({"string_field": "foo", "int_field": 42})
    )

    assert response.status == 200


async def test_unsupported_content_type(app_with_accepts, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_accepts)
    response = await client.post(
        "/", data=json.dumps({"string_field": "foo", "int_field": 42}), headers={"Content-Type": "text/plain"}
    )

    assert response.status == 415


async def test_invalid_json(app_with_accepts, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_accepts)
    response = await client.post("/", json="asdfasdf")
    assert response.status == 400


@pytest.fixture()
def app_with_accepts_no_request_param(aiohttp_apistrap):
    app = web.Application()
    routes = web.RouteTableDef()

    @routes.post("/")
    @aiohttp_apistrap.accepts(RequestModel)
    async def view(req: RequestModel):
        assert req.string_field == "foo"
        assert req.int_field == 42
        return web.Response(content_type="application/json", text=json.dumps({"status": "OK"}))

    app.add_routes(routes)
    aiohttp_apistrap.init_app(app)
    yield app


async def test_accepts_no_request_param(app_with_accepts_no_request_param, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_accepts_no_request_param)
    response = await client.post(
        "/", headers={"content-type": "application/json"}, data=json.dumps({"string_field": "foo", "int_field": 42})
    )

    assert response.status == 200


@pytest.fixture()
def app_with_accepts_form(aiohttp_apistrap):
    app = web.Application()
    routes = web.RouteTableDef()

    @routes.post("/")
    @aiohttp_apistrap.accepts(RequestModel, mimetypes=["application/x-www-form-urlencoded"])
    async def view(req: RequestModel):
        assert req.string_field == "foo"
        assert req.int_field == 42
        return web.Response(content_type="application/json", text="{}")

    app.add_routes(routes)
    aiohttp_apistrap.init_app(app)

    yield app


async def test_form_parameter_in_spec_json(app_with_accepts_form, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_accepts_form)
    response = await client.get("/spec.json")
    json = await response.json()

    assert "components" in json
    assert "schemas" in json["components"]

    path = json["paths"]["/"]["post"]

    body = path["requestBody"]
    assert body is not None
    assert body["required"] is True
    assert "application/x-www-form-urlencoded" in body["content"]


async def test_accepting_form(app_with_accepts_form, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_accepts_form)

    response = await client.post(
        "/",
        data={"int_field": "42", "string_field": "foo"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status == 200
    assert await response.json() == {}
