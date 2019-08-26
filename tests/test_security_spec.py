import pytest

from apistrap.extension import OAuthSecurity, OAuthFlowDefinition
from apistrap.flask import FlaskApistrap


@pytest.fixture()
def app_with_oauth(app):
    oapi = FlaskApistrap()
    oapi.add_security_scheme(
        OAuthSecurity(
            "oauth",
            lambda scopes: None,
            OAuthFlowDefinition(
                "authorization_code", {"read": "Read stuff", "write": "Write stuff"}, "/auth", "/token"
            ),
        )
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

    assert response.json["paths"]["/secured"]["get"]["security"] == {"oauth": ["read"]}
