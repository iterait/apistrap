import json

import pytest
from aiohttp import web

from apistrap.aiohttp import AioHTTPApistrap


async def test_aiohttp_spec_url_repeated_call(aiohttp_client):
    oapi = AioHTTPApistrap()

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
    response = await client.get('/spec.json')

    assert response.status == 200
    data = await response.json()
    assert 'paths' in data
    assert '/' in data['paths']

    response = await client.get('/spec.json')

    assert response.status == 200
    new_data = await response.json()
    assert new_data == data


async def test_aiohttp_spec_url_weird_method(aiohttp_client):
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.route('options', '/')
    @routes.get('/')
    async def view(request):
        return web.Response(content_type="application/json", text=json.dumps({
            "status": "OK"
        }))

    app.add_routes(routes)

    client = await aiohttp_client(app)
    response = await client.get('/spec.json')

    assert response.status == 200
    data = await response.json()
    assert 'paths' in data
    assert '/' in data['paths']
    assert 'options' not in data['paths']['/']


async def test_aiohttp_spec_url_with_params(aiohttp_client):
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get('/{param}/')
    async def view(request):
        return web.Response(content_type="application/json", text=json.dumps({
            "status": "OK"
        }))

    app.add_routes(routes)

    client = await aiohttp_client(app)
    response = await client.get('/spec.json')

    assert response.status == 200
    data = await response.json()
    assert 'paths' in data
    assert data['paths']['/{param}/']['get']['parameters'][0]['name'] == 'param'


async def test_aiohttp_spec_url_ignore_endpoint(aiohttp_client):
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get('/')
    @oapi.ignore()
    async def view(request):
        return web.Response(content_type="application/json", text=json.dumps({
            "status": "OK"
        }))

    app.add_routes(routes)

    client = await aiohttp_client(app)
    response = await client.get('/spec.json')

    assert response.status == 200
    data = await response.json()
    assert 'paths' in data
    assert '/' not in data['paths']
