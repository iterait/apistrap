import json
from typing import Sequence

import pytest
from aiohttp import web
from aiohttp.web_request import BaseRequest

from apistrap.aiohttp import AioHTTPApistrap
from apistrap.extension import OAuthFlowDefinition, OAuthSecurity
from apistrap.schemas import ErrorResponse


def rw_allowing_enforcer(request: BaseRequest, scopes: Sequence[str]):
    user_scopes = ["read", "write"]

    if not all((scope in user_scopes) for scope in scopes):
        raise ForbiddenRequestError()


async def async_rw_allowing_enforcer(request: BaseRequest, scopes: Sequence[str]):
    rw_allowing_enforcer(request, scopes)


class ForbiddenRequestError(Exception):
    pass


@pytest.fixture(params=[rw_allowing_enforcer, async_rw_allowing_enforcer])
async def app_with_oauth(request):
    app = web.Application()
    routes = web.RouteTableDef()

    oapi = AioHTTPApistrap()
    oapi.add_security_scheme(
        OAuthSecurity(
            "oauth",
            OAuthFlowDefinition(
                "authorization_code",
                {"read": "Read stuff", "write": "Write stuff", "frobnicate": "Frobnicate stuff"},
                "/auth",
                "/token",
            ),
        ),
        request.param,
    )

    oapi.add_error_handler(ForbiddenRequestError, 403, lambda _: ErrorResponse())

    @routes.get("/secured")
    @oapi.security("read")
    async def secured():
        return web.Response(content_type="application/json", text=json.dumps({}))

    @routes.get("/secured_multiple")
    @oapi.security("read", "write")
    async def multi():
        return web.Response(content_type="application/json", text=json.dumps({}))

    @routes.get("/forbidden")
    @oapi.security("frobnicate")
    async def forbidden():
        return web.Response(content_type="application/json", text=json.dumps({}))

    app.add_routes(routes)
    oapi.init_app(app)
    yield app


@pytest.fixture(params=[rw_allowing_enforcer, async_rw_allowing_enforcer])
async def app_with_oauth_and_unsecured_endpoint(request):
    app = web.Application()
    routes = web.RouteTableDef()

    oapi = AioHTTPApistrap()
    oapi.add_security_scheme(
        OAuthSecurity(
            "oauth",
            OAuthFlowDefinition(
                "authorization_code",
                {"read": "Read stuff", "write": "Write stuff", "frobnicate": "Frobnicate stuff"},
                "/auth",
                "/token",
            ),
        ),
        request.param,
    )

    oapi.add_error_handler(ForbiddenRequestError, 403, lambda _: ErrorResponse())

    @routes.get("/unsecured")
    async def unsecured():
        return web.Response(content_type="application/json", text=json.dumps({}))

    app.add_routes(routes)
    oapi.init_app(app)
    yield app


async def test_security_enforcement_single_scope(app_with_oauth, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_oauth)
    response = await client.get("/secured")
    assert response.status == 200


async def test_security_enforcement_multiple_scopes(app_with_oauth, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_oauth)
    response = await client.get("/secured_multiple")
    assert response.status == 200


async def test_security_enforcement_forbidden(app_with_oauth, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_oauth)
    response = await client.get("/forbidden")
    assert response.status == 403


async def test_security_enforcement_unsecured_endpoint_spec(
    app_with_oauth_and_unsecured_endpoint, aiohttp_initialized_client
):
    client = await aiohttp_initialized_client(app_with_oauth_and_unsecured_endpoint)
    response = await client.get("/spec.json")
    assert response.status == 200


async def test_security_enforcement_unsecured_endpoint(
    app_with_oauth_and_unsecured_endpoint, aiohttp_initialized_client
):
    client = await aiohttp_initialized_client(app_with_oauth_and_unsecured_endpoint)
    response = await client.get("/unsecured")
    assert response.status == 200
