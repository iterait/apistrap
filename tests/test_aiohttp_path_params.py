import json

import pytest
from aiohttp import web
from aiohttp.web_request import Request

from apistrap.aiohttp import AioHTTPApistrap


@pytest.fixture(scope="function")
def app_without_request_param():
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get("/")
    async def view():
        return web.Response(content_type="application/json", text=json.dumps({"status": "OK"}))

    app.add_routes(routes)

    yield app


async def test_aiohttp_spec_no_request_param_spec(app_without_request_param, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_without_request_param)
    response = await client.get("/spec.json")

    assert response.status == 200
    data = await response.json()
    assert "paths" in data
    assert "/" in data["paths"]

    response = await client.get("/spec.json")

    assert response.status == 200
    new_data = await response.json()
    assert new_data == data


async def test_aiohttp_spec_no_request_param_invocation(app_without_request_param, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_without_request_param)
    response = await client.get("/")

    assert response.status == 200
    data = await response.json()

    assert data == {"status": "OK"}


@pytest.fixture(scope="function")
def app_with_params_as_args():
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get("/{param_a}/{param_b}")
    async def view(param_a: str, param_b: int):
        return web.Response(content_type="application/json", text=json.dumps({"a": param_a, "b": param_b}))

    app.add_routes(routes)

    yield app


async def test_aiohttp_path_params_as_args_spec(aiohttp_initialized_client, app_with_params_as_args):
    client = await aiohttp_initialized_client(app_with_params_as_args)
    response = await client.get("/spec.json")

    assert response.status == 200
    data = await response.json()

    parameters = data["paths"]["/{param_a}/{param_b}"]["get"]["parameters"]
    assert len(parameters) == 2

    param_a = next(filter(lambda p: p["name"] == "param_a", parameters), None)
    param_b = next(filter(lambda p: p["name"] == "param_b", parameters), None)

    assert param_a == {"in": "path", "name": "param_a", "required": True, "schema": {"type": "string"}}
    assert param_b == {"in": "path", "name": "param_b", "required": True, "schema": {"type": "integer"}}


async def test_aiohttp_path_params_as_args_arg_assignment(aiohttp_initialized_client, app_with_params_as_args):
    client = await aiohttp_initialized_client(app_with_params_as_args)
    response = await client.get("/a/42")

    assert response.status == 200
    data = await response.json()

    assert data == {"a": "a", "b": 42}


@pytest.fixture(scope="function")
def app_with_optional_parameter():
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get("/")
    @routes.get("/{param}")
    async def view(param: str = "Default"):
        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {
                    "param": param,
                }
            ),
        )

    app.add_routes(routes)

    yield app


async def test_aiohttp_path_param_optional_spec(aiohttp_initialized_client, app_with_optional_parameter):
    client = await aiohttp_initialized_client(app_with_optional_parameter)
    response = await client.get("spec.json")

    assert response.status == 200
    data = await response.json()

    assert len(data["paths"]) == 2


async def test_aiohttp_path_param_optional_invocation(aiohttp_initialized_client, app_with_optional_parameter):
    client = await aiohttp_initialized_client(app_with_optional_parameter)
    response = await client.get("/value")

    assert response.status == 200
    data = await response.json()

    assert data["param"] == "value"


async def test_aiohttp_path_param_optional_invocation_default(aiohttp_initialized_client, app_with_optional_parameter):
    client = await aiohttp_initialized_client(app_with_optional_parameter)
    response = await client.get("/")

    assert response.status == 200
    data = await response.json()

    assert data["param"] == "Default"


async def test_aiohttp_path_param_multiple_request_parameters(aiohttp_initialized_client):
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    with pytest.raises(TypeError):

        @routes.get("/")
        @routes.get("/{param}")
        async def view(request_1: Request, request_2: Request, param: str = "Default"):
            return web.Response(
                content_type="application/json",
                text=json.dumps(
                    {
                        "param": param,
                    }
                ),
            )

        app.add_routes(routes)

        client = await aiohttp_initialized_client(app)
        await client.get("/spec.json")


async def test_aiohttp_path_param_unsupported_parameter(aiohttp_initialized_client):
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    with pytest.raises(TypeError):

        @routes.get("/{param}")
        async def view(param: dict):
            return web.Response(
                content_type="application/json",
                text=json.dumps(
                    {
                        "param": param,
                    }
                ),
            )

        app.add_routes(routes)

        client = await aiohttp_initialized_client(app)
        await client.get("/spec.json")


@pytest.fixture(scope="function")
def app_with_unannotated_parameter():
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get("/{param}")
    async def view(param):
        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {
                    "param": param,
                }
            ),
        )

    app.add_routes(routes)

    yield app


async def test_aiohttp_path_unannotated_parameter_spec(aiohttp_initialized_client, app_with_unannotated_parameter):
    client = await aiohttp_initialized_client(app_with_unannotated_parameter)
    response = await client.get("/spec.json")

    assert response.status == 200
    data = await response.json()

    parameters = data["paths"]["/{param}"]["get"]["parameters"]
    assert parameters == [{"in": "path", "name": "param", "required": True, "schema": {"type": "string"}}]


async def test_aiohttp_path_unannotated_parameter_arg_assignment(
    aiohttp_initialized_client, app_with_unannotated_parameter
):
    client = await aiohttp_initialized_client(app_with_unannotated_parameter)
    response = await client.get("/42")

    assert response.status == 200
    data = await response.json()

    assert data == {"param": "42"}


async def test_aiohttp_path_params_invalid_value(aiohttp_initialized_client, app_with_params_as_args):
    client = await aiohttp_initialized_client(app_with_params_as_args)
    response = await client.get("/a/foobar")

    assert response.status == 400
