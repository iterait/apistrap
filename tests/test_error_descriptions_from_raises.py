import pytest

from apistrap.flask import FlaskApistrap
from apistrap.schemas import ErrorResponse


@pytest.fixture()
def app_with_raises(app):
    oapi = FlaskApistrap()

    @app.route("/", methods=["GET"])
    def view():
        """
        Something something.

        :raises KeyError: KeyError description
        """

    oapi.init_app(app)


@pytest.fixture()
def app_with_raises_and_handler(app):
    oapi = FlaskApistrap()
    oapi.add_error_handler(KeyError, 515, lambda e: ErrorResponse())

    @app.route("/", methods=["GET"])
    def view():
        """
        Something something.

        :raises KeyError: KeyError description
        """

    oapi.init_app(app)


def test_error_descriptions_from_raises(app_with_raises, client):
    response = client.get("/spec.json")

    assert response.json["paths"]["/"]["get"]["responses"] == {
        "500": {
            "description": "KeyError description",
            "content": {
                "application/json": {
                    "type": "object",
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    }
                }
            }
        }
    }


def test_http_code_from_handler(app_with_raises_and_handler, client):
    response = client.get("/spec.json")

    assert response.json["paths"]["/"]["get"]["responses"] == {
        "515": {
            "description": "KeyError description",
            "content": {
                "application/json": {
                    "type": "object",
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    }
                }
            }
        }
    }
