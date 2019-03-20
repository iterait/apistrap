import pytest
from flask import jsonify

from apistrap.errors import SwaggerExtensionError
from apistrap.flask import FlaskApistrap


def test_swagger_extension_definition_conflict_1():
    with pytest.raises(ValueError):
        swagger = FlaskApistrap()
        swagger.add_response_definition("name", {"foo": "bar"})
        swagger.add_response_definition("name", {"baz": "bar"})


def test_swagger_extension_definition_conflict_2():
    with pytest.raises(ValueError):
        swagger = FlaskApistrap()
        swagger.add_request_definition("name", {"foo": "bar"})
        swagger.add_request_definition("name", {"baz": "bar"})


def test_getters():
    swagger = FlaskApistrap()
    swagger.title = "Title"
    swagger.description = "Description"
    assert swagger.title == "Title"
    assert swagger.description == "Description"


def test_spec_url(app, client):
    swagger = FlaskApistrap()

    swagger.spec_url = "/myspecurl.json"
    assert swagger.spec_url == "/myspecurl.json"

    swagger.init_app(app)

    @app.route("/")
    def view():
        return jsonify()

    response = client.get("/myspecurl.json")
    assert response.status_code == 200
    assert "paths" in response.json


def test_spec_url_reset(app, client):
    swagger = FlaskApistrap()

    swagger.spec_url = None
    assert swagger.spec_url is None

    swagger.spec_url = "/myspecurl.json"
    assert swagger.spec_url == "/myspecurl.json"

    swagger.init_app(app)

    @app.route("/")
    def view():
        return jsonify()

    response = client.get("/myspecurl.json")
    assert response.status_code == 200
    assert "paths" in response.json


def test_spec_url_cannot_be_set_after_init(app):
    swagger = FlaskApistrap()
    swagger.init_app(app)
    with pytest.raises(SwaggerExtensionError):
        swagger.spec_url = "whatever"


def test_disable_spec_url(app, client):
    swagger = FlaskApistrap()

    swagger.spec_url = None
    assert swagger.spec_url is None

    swagger.init_app(app)

    @app.route("/")
    def view():
        return jsonify()

    response = client.get("/swagger.json")
    assert response.status_code == 404


def test_disable_ui(app, client):
    swagger = FlaskApistrap()
    swagger.ui_url = None
    assert swagger.ui_url is None
    swagger.init_app(app)

    response = client.get("/apidocs/")
    assert response.status_code == 404


def test_ui_url_cannot_be_set_after_init(app):
    swagger = FlaskApistrap()
    swagger.init_app(app)
    with pytest.raises(SwaggerExtensionError):
        swagger.ui_url = None


def test_set_ui_url(app, client):
    swagger = FlaskApistrap()

    swagger.ui_url = "/docs/"
    assert swagger.ui_url == "/docs" or swagger.ui_url == "/docs/"

    swagger.init_app(app)

    response = client.get("/docs/")
    print(response.json)
    assert response.status_code == 200
