import pytest
import json

from aiohttp import web

from apistrap.aiohttp import AioHTTPApistrap


@pytest.fixture(scope="function")
def app_with_params_as_args():
    oapi = AioHTTPApistrap()

    app = web.Application()
    routes = web.RouteTableDef()
    oapi.init_app(app)

    @routes.get('/{param_a}/{param_b}')
    async def view(param_a: str, param_b: int):
        """
        A cool view handler.

        :param param_a: Parameter A
        :param param_b: Parameter B
        """

        return web.Response(content_type="application/json", text=json.dumps({
            "a": param_a,
            "b": param_b
        }))

    app.add_routes(routes)

    yield app


async def test_summary_from_docblock(app_with_params_as_args, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_params_as_args)
    response = await client.get("/spec.json")

    assert response.status == 200
    data = await response.json()
    path = data["paths"]["/{param_a}/{param_b}"]["get"]

    assert path["summary"] == "A cool view handler."


async def test_parameters_from_docblock(app_with_params_as_args, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_params_as_args)
    response = await client.get("/spec.json")

    assert response.status == 200
    data = await response.json()
    path = data["paths"]["/{param_a}/{param_b}"]["get"]

    param_a = next(filter(lambda p: p["name"] == "param_a", path["parameters"]), None)
    param_b = next(filter(lambda p: p["name"] == "param_b", path["parameters"]), None)

    assert param_a["description"] == "Parameter A"
    assert param_b["description"] == "Parameter B"
