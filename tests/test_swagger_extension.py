import pytest
from flask import jsonify

from apistrap import Swagger
from apistrap.errors import SwaggerExtensionError


def test_swagger_extension_definition_conflict():
    with pytest.raises(ValueError):
        swagger = Swagger()
        swagger.add_definition("name", {"foo": "bar"})
        swagger.add_definition("name", {"baz": "bar"})


def test_getters():
    swagger = Swagger()
    swagger.title = "Title"
    swagger.description = "Description"
    assert swagger.title == "Title"
    assert swagger.description == "Description"


def test_spec_url(app, client):
    swagger = Swagger()

    swagger.spec_url = "/myspecurl.json"
    assert swagger.spec_url == "/myspecurl.json"

    swagger.init_app(app)

    @app.route("/")
    @swagger.autodoc()
    def view():
        return jsonify()

    response = client.get("/myspecurl.json")
    assert response.status_code == 200
    assert "paths" in response.json


def test_spec_url_reset(app, client):
    swagger = Swagger()

    swagger.spec_url = None
    assert swagger.spec_url is None

    swagger.spec_url = "/myspecurl.json"
    assert swagger.spec_url == "/myspecurl.json"

    swagger.init_app(app)

    @app.route("/")
    @swagger.autodoc()
    def view():
        return jsonify()

    response = client.get("/myspecurl.json")
    assert response.status_code == 200
    assert "paths" in response.json


def test_spec_url_cannot_be_set_after_init(app):
    swagger = Swagger(app)
    with pytest.raises(SwaggerExtensionError):
        swagger.spec_url = "whatever"


def test_disable_spec_url(app, client):
    swagger = Swagger()

    swagger.spec_url = None
    assert swagger.spec_url is None

    swagger.init_app(app)

    @app.route("/")
    @swagger.autodoc()
    def view():
        return jsonify()

    response = client.get("/swagger.json")
    assert response.status_code == 404


def test_disable_ui(app, client):
    swagger = Swagger()
    swagger.ui_url = None
    assert swagger.ui_url is None
    swagger.init_app(app)

    response = client.get("/apidocs/")
    assert response.status_code == 404


def test_ui_url_cannot_be_set_after_init(app):
    swagger = Swagger(app)
    with pytest.raises(SwaggerExtensionError):
        swagger.ui_url = None


def test_set_ui_url(app, client):
    swagger = Swagger()

    swagger.ui_url = "/docs/"
    assert swagger.ui_url == "/docs/"

    swagger.init_app(app)

    response = client.get("/docs/")
    assert response.status_code == 200
