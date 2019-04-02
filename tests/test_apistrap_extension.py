import pytest
from flask import jsonify

from apistrap.errors import ApistrapExtensionError
from apistrap.flask import FlaskApistrap


def test_apistrap_extension_definition_conflict_1():
    with pytest.raises(ValueError):
        oapi = FlaskApistrap()
        oapi.add_response_definition("name", {"foo": "bar"})
        oapi.add_response_definition("name", {"baz": "bar"})


def test_apistrap_extension_definition_conflict_2():
    with pytest.raises(ValueError):
        oapi = FlaskApistrap()
        oapi.add_request_definition("name", {"foo": "bar"})
        oapi.add_request_definition("name", {"baz": "bar"})


def test_getters():
    oapi = FlaskApistrap()
    oapi.title = "Title"
    oapi.description = "Description"
    assert oapi.title == "Title"
    assert oapi.description == "Description"


def test_spec_url(app, client):
    oapi = FlaskApistrap()

    oapi.spec_url = "/myspecurl.json"
    assert oapi.spec_url == "/myspecurl.json"

    oapi.init_app(app)

    @app.route("/")
    def view():
        return jsonify()

    response = client.get("/myspecurl.json")
    assert response.status_code == 200
    assert "paths" in response.json


def test_spec_url_reset(app, client):
    oapi = FlaskApistrap()

    oapi.spec_url = None
    assert oapi.spec_url is None

    oapi.spec_url = "/myspecurl.json"
    assert oapi.spec_url == "/myspecurl.json"

    oapi.init_app(app)

    @app.route("/")
    def view():
        return jsonify()

    response = client.get("/myspecurl.json")
    assert response.status_code == 200
    assert "paths" in response.json


def test_spec_url_cannot_be_set_after_init(app):
    oapi = FlaskApistrap()
    oapi.init_app(app)
    with pytest.raises(ApistrapExtensionError):
        oapi.spec_url = "whatever"


def test_disable_spec_url(app, client):
    oapi = FlaskApistrap()

    oapi.spec_url = None
    assert oapi.spec_url is None

    oapi.init_app(app)

    @app.route("/")
    def view():
        return jsonify()

    response = client.get("/spec.json")
    assert response.status_code == 404


def test_disable_ui(app, client):
    oapi = FlaskApistrap()
    oapi.ui_url = None
    assert oapi.ui_url is None
    oapi.init_app(app)

    response = client.get("/apidocs/")
    assert response.status_code == 404


def test_ui_url_cannot_be_set_after_init(app):
    oapi = FlaskApistrap()
    oapi.init_app(app)
    with pytest.raises(ApistrapExtensionError):
        oapi.ui_url = None


def test_set_ui_url(app, client):
    oapi = FlaskApistrap()

    oapi.ui_url = "/docs/"
    assert oapi.ui_url == "/docs" or oapi.ui_url == "/docs/"

    oapi.init_app(app)

    response = client.get("/docs/")
    assert response.status_code == 200
