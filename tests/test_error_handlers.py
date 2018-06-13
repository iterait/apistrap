import pytest

from apistrap import Swagger
from apistrap.errors import ApiClientError, ApiServerError


@pytest.fixture()
def app_with_errors(app, swagger):
    @app.route("/client_error")
    def view_1():
        raise ApiClientError()

    @app.route("/server_error")
    def view_2():
        raise ApiServerError()

    @app.route("/internal_error")
    def view_3():
        raise RuntimeError("Runtime error occurred")


def test_http_error_handler(app_with_errors, client):
    response = client.get("/nonexistent_url")
    assert response.status_code == 404
    assert 'debug_data' not in response.json


def test_http_error_handler_in_production(app_with_errors, client, app_in_production):
    response = client.get("/nonexistent_url")
    assert response.status_code == 404
    assert 'debug_data' not in response.json


def test_client_error_handler(app_with_errors, client):
    response = client.get("/client_error")
    assert response.status_code == 400
    assert 'debug_data' in response.json
    assert response.json['debug_data']['exception_type'] == 'ApiClientError'


def test_client_error_handler_in_production(app_with_errors, client, app_in_production):
    response = client.get("/client_error")
    assert response.status_code == 400
    assert 'debug_data' not in response.json


def test_server_error_handler(app_with_errors, client):
    response = client.get("/server_error")
    assert response.status_code == 500
    assert 'debug_data' in response.json
    assert response.json['debug_data']['exception_type'] == 'ApiServerError'


def test_server_error_handler_in_production(app_with_errors, client, app_in_production):
    response = client.get("/server_error")
    assert response.status_code == 500
    assert 'debug_data' not in response.json


def test_internal_server_error_handler(app_with_errors, client):
    response = client.get("/internal_error")
    assert response.status_code == 500
    assert response.json["message"] == "Runtime error occurred"
    assert 'debug_data' in response.json
    assert response.json['debug_data']['exception_type'] == 'RuntimeError'


def test_internal_server_error_handler_in_production(app_with_errors, client, app_in_production):
    response = client.get("/internal_error")
    assert response.status_code == 500
    assert response.json["message"] == "Internal server error"


@pytest.fixture()
def app_with_errors_and_no_error_handlers(app):
    swagger = Swagger()
    swagger.use_default_error_handlers = False
    swagger.init_app(app)

    @app.route("/internal_error")
    def view():
        raise RuntimeError("Runtime error occurred")


def test_disabled_default_error_handlers(app_with_errors_and_no_error_handlers, client):
    with pytest.raises(RuntimeError):
        client.get("/internal_error")
