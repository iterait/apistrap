import pytest
from aiohttp import web

from apistrap.aiohttp import AioHTTPApistrap


async def test_aiohttp_title_in_spec_json(aiohttp_client):
    oapi = AioHTTPApistrap()
    app = web.Application()
    oapi.init_app(app)
    oapi.title = "A title"

    client = await aiohttp_client(app)
    response = await client.get("/spec.json")
    assert response.status == 200

    data = await response.json()
    assert data["info"]["title"] == "A title"


async def test_aiohttp_description_in_spec_json(aiohttp_client):
    oapi = AioHTTPApistrap()
    app = web.Application()
    oapi.init_app(app)
    oapi.description = "A description"

    client = await aiohttp_client(app)
    response = await client.get("/spec.json")
    assert response.status == 200

    data = await response.json()
    assert data["info"]["description"] == "A description"
