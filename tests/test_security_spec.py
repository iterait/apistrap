import pytest

from apistrap.extension import OAuthFlowDefinition, OAuthSecurity
from apistrap.flask import FlaskApistrap


@pytest.fixture()
def app_with_oauth(app):
    oapi = FlaskApistrap()
    oapi.add_security_scheme(
        OAuthSecurity(
            "oauth",
            OAuthFlowDefinition(
                "authorization_code", {"read": "Read stuff", "write": "Write stuff"}, "/auth", "/token"
            ),
        ),
        lambda scopes: None
    )

    @app.route("/secured", methods=["GET"])
    @oapi.security("read")
    def view():
        pass

    oapi.init_app(app)


def test_security_spec(app_with_oauth, client):
    response = client.get("/spec.json")

    assert len(response.json["components"]["securitySchemes"]) == 1

    assert response.json["components"]["securitySchemes"]["oauth"] == {
        "type": "oauth2",
        "flows": {
            "authorization_code": {
                "authorizationUrl": "/auth",
                "tokenUrl": "/token",
                "scopes": {"read": "Read stuff", "write": "Write stuff"},
            }
        },
    }

    assert response.json["paths"]["/secured"]["get"]["security"] == [{"oauth": ["read"]}]


class Scope:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return other.name == self.name


@pytest.fixture()
def app_with_oauth_non_string_scopes(app):
    oapi = FlaskApistrap()
    oapi.add_security_scheme(
        OAuthSecurity(
            "oauth",
            OAuthFlowDefinition(
                "authorization_code", {"read": "Read stuff", "write": "Write stuff"}, "/auth", "/token"
            ),
        ),
        lambda scopes: None
    )

    @app.route("/secured", methods=["GET"])
    @oapi.security(Scope("read"))
    def view():
        pass

    oapi.init_app(app)


def test_security_spec_non_string_scopes(app_with_oauth_non_string_scopes, client):
    response = client.get("/spec.json")
    assert response.status_code == 200

    assert len(response.json["components"]["securitySchemes"]) == 1

    assert response.json["components"]["securitySchemes"]["oauth"] == {
        "type": "oauth2",
        "flows": {
            "authorization_code": {
                "authorizationUrl": "/auth",
                "tokenUrl": "/token",
                "scopes": {"read": "Read stuff", "write": "Write stuff"},
            }
        },
    }

    assert response.json["paths"]["/secured"]["get"]["security"] == [{"oauth": ["read"]}]
