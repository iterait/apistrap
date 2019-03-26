import json

import pytest
from aiohttp import web
from aiohttp.web_request import BaseRequest
from schematics import Model
from schematics.types import IntType, StringType


class RequestModel(Model):
    string_field: str = StringType(required=True)
    int_field: int = IntType(required=True)


@pytest.fixture()
def app_with_accepts(aiohttp_apistrap):
    app = web.Application()
    routes = web.RouteTableDef()

    @routes.post("/")
    @aiohttp_apistrap.accepts(RequestModel)
    async def view(aiohttp_request, req: RequestModel):
        assert isinstance(aiohttp_request, BaseRequest)
        assert req.string_field == "foo"
        assert req.int_field == 42
        return web.Response(content_type="application/json", text=json.dumps({
            "status": "OK"
        }))

    app.add_routes(routes)
    yield app


async def test_accepts(app_with_accepts, aiohttp_client):
    client = await aiohttp_client(app_with_accepts)
    response = await client.post("/", headers={"content-type": "application/json"}, data=json.dumps({
        "string_field": "foo",
        "int_field": 42
    }))

    assert response.status == 200
