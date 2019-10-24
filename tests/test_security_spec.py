import pytest

from apistrap.errors import ApistrapExtensionError
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
        lambda scopes: None,
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
        lambda scopes: None,
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


def test_security_spec_multiple_schemes_default(app, client):
    oapi = FlaskApistrap()

    scheme_1 = OAuthSecurity(
        "oauth_1",
        OAuthFlowDefinition("authorization_code", {"read": "Read stuff", "write": "Write stuff"}, "/auth", "/token"),
    )
    scheme_2 = OAuthSecurity(
        "oauth_2",
        OAuthFlowDefinition("authorization_code", {"read": "Read stuff", "write": "Write stuff"}, "/auth", "/token"),
    )

    oapi.add_security_scheme(scheme_1, lambda _: None)
    oapi.add_security_scheme(scheme_2, lambda _: None, default=True)

    assert oapi.default_security_scheme == scheme_2

    @app.route("/secured", methods=["GET"])
    @oapi.security("read")
    def view_1():
        pass

    @app.route("/also_secured", methods=["GET"])
    @oapi.security("read", scheme=scheme_1)
    def view_2():
        pass

    oapi.init_app(app)

    response = client.get("/spec.json")
    assert response.status_code == 200

    assert response.json["paths"]["/secured"]["get"]["security"] == [{"oauth_2": ["read"]}]
    assert response.json["paths"]["/also_secured"]["get"]["security"] == [{"oauth_1": ["read"]}]


def test_security_spec_multiple_schemes_default_conflict():
    oapi = FlaskApistrap()

    scheme_1 = OAuthSecurity(
        "oauth_1",
        OAuthFlowDefinition("authorization_code", {"read": "Read stuff", "write": "Write stuff"}, "/auth", "/token"),
    )
    scheme_2 = OAuthSecurity(
        "oauth_2",
        OAuthFlowDefinition("authorization_code", {"read": "Read stuff", "write": "Write stuff"}, "/auth", "/token"),
    )

    oapi.add_security_scheme(scheme_1, lambda _: None, default=True)

    with pytest.raises(ApistrapExtensionError):
        oapi.add_security_scheme(scheme_2, lambda _: None, default=True)


def test_security_spec_multiple_schemes_no_default(app, client):
    oapi = FlaskApistrap()

    scheme_1 = OAuthSecurity(
        "oauth_1",
        OAuthFlowDefinition("authorization_code", {"read": "Read stuff", "write": "Write stuff"}, "/auth", "/token"),
    )
    scheme_2 = OAuthSecurity(
        "oauth_2",
        OAuthFlowDefinition("authorization_code", {"read": "Read stuff", "write": "Write stuff"}, "/auth", "/token"),
    )

    oapi.add_security_scheme(scheme_1, lambda _: None)
    oapi.add_security_scheme(scheme_2, lambda _: None)

    @app.route("/asdf")
    @oapi.security()
    def secured():
        return "asdf"

    oapi.use_default_error_handlers = False

    with pytest.raises(TypeError):
        oapi.init_app(app)
        client.get("/spec.json")


def test_security_spec_no_scheme(app, client):
    oapi = FlaskApistrap()

    @app.route("/asdf")
    @oapi.security()
    def secured():
        return "asdf"

    oapi.use_default_error_handlers = False

    with pytest.raises(TypeError):
        oapi.init_app(app)
        client.get("/spec.json")
