from typing import List

import pytest
from flask import jsonify

from apistrap.extension import OAuthFlowDefinition, OAuthSecurity
from apistrap.flask import FlaskApistrap
from apistrap.schemas import ErrorResponse


def enforcer(scopes: List[str]):
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
            enforcer,
            OAuthFlowDefinition(
                "authorization_code",
                {"read": "Read stuff", "write": "Write stuff", "frobnicate": "Frobnicate stuff"},
                "/auth",
                "/token",
            ),
        )
    )

    oapi.add_error_handler(ForbiddenRequestError, 403, lambda _: ErrorResponse())

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


def test_security_enforcement_single_scope(app_with_oauth, client):
    response = client.get("/secured")
    assert response.status_code == 200


def test_security_enforcement_multiple_scopes(app_with_oauth, client):
    response = client.get("/secured_multiple")
    assert response.status_code == 200


def test_security_enforcement_forbidden(app_with_oauth, client):
    response = client.get("/forbidden")
    assert response.status_code == 403
