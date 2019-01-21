import pytest
from aiohttp import web

from apistrap.errors import ApiClientError, ApiServerError


@pytest.fixture()
def error_routes():
    routes = web.RouteTableDef()

    @routes.get('/client_error')
    def view_1(request):
        raise ApiClientError()

    @routes.get('/server_error')
    def view_2(request):
        raise ApiServerError()

    @routes.get('/internal_error')
    def view_3(request):
        raise RuntimeError('Runtime error occurred')

    yield routes


@pytest.fixture()
def app_with_errors(aiohttp_apistrap, error_routes):
    app = web.Application(debug=True)
    app.add_routes(error_routes)
    aiohttp_apistrap.init_app(app)
    yield app


@pytest.fixture()
def app_with_errors_in_production(aiohttp_apistrap, error_routes):
    app = web.Application(debug=False)
    app.add_routes(error_routes)
    aiohttp_apistrap.init_app(app)
    yield app


async def test_http_error_handler(app_with_errors, aiohttp_client):
    client = await aiohttp_client(app_with_errors)
    response = await client.get('/nonexistent_url')
    assert response.status == 404
    data = await response.json()
    assert 'debug_data' not in data


async def test_http_error_handler_in_production(app_with_errors_in_production, aiohttp_client):
    client = await aiohttp_client(app_with_errors_in_production)
    response = await client.get('/nonexistent_url')
    assert response.status == 404
    data = await response.json()
    assert 'debug_data' not in data


async def test_client_error_handler(app_with_errors, aiohttp_client):
    client = await aiohttp_client(app_with_errors)
    response = await client.get('/client_error')
    assert response.status == 400
    data = await response.json()
    assert 'debug_data' in data
    assert data['debug_data']['exception_type'] == 'ApiClientError'


async def test_client_error_handler_in_production(app_with_errors_in_production, aiohttp_client):
    client = await aiohttp_client(app_with_errors_in_production)
    response = await client.get('/client_error')
    assert response.status == 400
    data = await response.json()
    assert 'debug_data' not in data


async def test_server_error_handler(app_with_errors, aiohttp_client):
    client = await aiohttp_client(app_with_errors)
    response = await client.get('/server_error')
    assert response.status == 500
    data = await response.json()
    assert 'debug_data' in data
    assert data['debug_data']['exception_type'] == 'ApiServerError'


async def test_server_error_handler_in_production(app_with_errors_in_production, aiohttp_client):
    client = await aiohttp_client(app_with_errors_in_production)
    response = await client.get('/server_error')
    assert response.status == 500
    data = await response.json()
    assert 'debug_data' not in data


async def test_internal_server_error_handler(app_with_errors, aiohttp_client):
    client = await aiohttp_client(app_with_errors)
    response = await client.get('/internal_error')
    assert response.status == 500
    data = await response.json()
    assert data['message'] == 'Runtime error occurred'
    assert 'debug_data' in data
    assert data['debug_data']['exception_type'] == 'RuntimeError'


async def test_internal_server_error_handler_in_production(app_with_errors_in_production, aiohttp_client):
    client = await aiohttp_client(app_with_errors_in_production)
    response = await client.get('/internal_error')
    assert response.status == 500
    data = await response.json()
    assert data['message'] == 'Internal server error'
