from typing import Sequence

import pytest
from flask import jsonify

from apistrap.extension import OAuthFlowDefinition, OAuthSecurity
from apistrap.flask import FlaskApistrap
from apistrap.schemas import ErrorResponse


def enforcer(scopes: Sequence[str]):
    user_scopes = ["read", "write"]

    if not all((scope in user_scopes) for scope in scopes):
        raise ForbiddenRequestError()


class ForbiddenRequestError(Exception):
    pass


@pytest.fixture()
def app_with_oauth(app):
    oapi = FlaskApistrap()
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
        enforcer,
    )

    oapi.add_error_handler(ForbiddenRequestError, 403, lambda _: ErrorResponse(message=""))

    @app.route("/secured", methods=["GET"])
    @oapi.security("read")
    def secured():
        return jsonify()

    @app.route("/secured_multiple", methods=["GET"])
    @oapi.security("read", "write")
    def multi():
        return jsonify()

    @app.route("/forbidden", methods=["GET"])
    @oapi.security("frobnicate")
    def forbidden():
        return jsonify()

    oapi.init_app(app)


@pytest.fixture()
def app_with_oauth_and_unsecured_endpoint(app):

    oapi = FlaskApistrap()
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
        enforcer,
    )

    oapi.add_error_handler(ForbiddenRequestError, 403, lambda _: ErrorResponse(message=""))

    @app.route("/unsecured", methods=["GET"])
    def unsecured():
        return jsonify()

    oapi.init_app(app)


def test_security_enforcement_single_scope(app_with_oauth, client):
    response = client.get("/secured")
    assert response.status_code == 200


def test_security_enforcement_multiple_scopes(app_with_oauth, client):
    response = client.get("/secured_multiple")
    assert response.status_code == 200


def test_security_enforcement_forbidden(app_with_oauth, client):
    response = client.get("/forbidden")
    assert response.status_code == 403


def test_security_enforcement_unsecured_endpoint_spec(app_with_oauth_and_unsecured_endpoint, client):
    response = client.get("/spec.json")
    assert response.status_code == 200


def test_security_enforcement_unsecured_endpoint(app_with_oauth_and_unsecured_endpoint, client):
    response = client.get("/unsecured")
    assert response.status_code == 200
