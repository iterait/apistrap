import pytest
import json

from apistrap.errors import ApistrapExtensionError
from apistrap.aiohttp import AioHTTPApistrap
from aiohttp import web


async def test_aiohttp_apistrap_extension_definition_conflict_1():
    with pytest.raises(ValueError):
        oapi = AioHTTPApistrap()
        oapi.add_response_definition("name", {"foo": "bar"})
        oapi.add_response_definition("name", {"baz": "bar"})


async def test_aiohttp_apistrap_extension_definition_conflict_2():
    with pytest.raises(ValueError):
        oapi = AioHTTPApistrap()
        oapi.add_request_definition("name", {"foo": "bar"})
        oapi.add_request_definition("name", {"baz": "bar"})


async def test_aiohttp_getters():
    oapi = AioHTTPApistrap()
    oapi.title = "Title"
    oapi.description = "Description"
    assert oapi.title == "Title"
    assert oapi.description == "Description"


async def test_aiohttp_spec_url(aiohttp_client):
    oapi = AioHTTPApistrap()

    oapi.spec_url = "/myspecurl.json"
    assert oapi.spec_url == "/myspecurl.json"

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get('/')
    async def view(request):
        return web.Response(content_type="application/json", text=json.dumps({
            "status": "OK"
        }))

    app.add_routes(routes)

    client = await aiohttp_client(app)
    response = await client.get("/myspecurl.json")

    assert response.status == 200

    data = await response.json()
    assert "paths" in data


async def test_aiohttp_spec_url_reset(aiohttp_client):
    oapi = AioHTTPApistrap()

    oapi.spec_url = None
    assert oapi.spec_url is None

    oapi.spec_url = "/myspecurl.json"
    assert oapi.spec_url == "/myspecurl.json"

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get('/')
    async def view(request):
        return web.Response(content_type="application/json", text=json.dumps({
            "status": "OK"
        }))

    app.add_routes(routes)

    client = await aiohttp_client(app)
    response = await client.get("/myspecurl.json")

    assert response.status == 200

    data = await response.json()
    assert "paths" in data


async def test_aiohttp_spec_url_cannot_be_set_after_init():
    oapi = AioHTTPApistrap()
    app = web.Application()
    oapi.init_app(app)
    with pytest.raises(ApistrapExtensionError):
        oapi.spec_url = "whatever"


async def test_aiohttp_disable_spec_url(aiohttp_client):
    oapi = AioHTTPApistrap()

    oapi.spec_url = None
    assert oapi.spec_url is None

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get('/')
    async def view(request):
        return web.Response(content_type="application/json", text=json.dumps({
            "status": "OK"
        }))

    app.add_routes(routes)

    client = await aiohttp_client(app)
    response = await client.get("/spec.json")
    assert response.status == 404


async def test_aiohttp_disable_ui(aiohttp_client):
    oapi = AioHTTPApistrap()

    oapi.ui_url = None
    assert oapi.ui_url is None

    app = web.Application()
    oapi.init_app(app)

    client = await aiohttp_client(app)
    response = await client.get("/apidocs/")
    assert response.status == 404


async def test_aiohttp_ui_url_cannot_be_set_after_init():
    oapi = AioHTTPApistrap()
    app = web.Application()
    oapi.init_app(app)
    with pytest.raises(ApistrapExtensionError):
        oapi.ui_url = None


async def test_aiohttp_set_ui_url(aiohttp_client):
    oapi = AioHTTPApistrap()

    oapi.ui_url = "/docs/"
    assert oapi.ui_url == "/docs" or oapi.ui_url == "/docs/"

    app = web.Application()
    oapi.init_app(app)

    client = await aiohttp_client(app)
    response = await client.get("/docs/")
    assert response.status == 200
