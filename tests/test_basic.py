import pytest
from flask import jsonify

from api_utils.decorators import autodoc


@pytest.fixture()
def app_basic(app):
    @app.route("/")
    @autodoc()
    def view():
        return jsonify()


def test_ui_accessible(app_basic, client):
    response = client.get("/apidocs/")
    assert response.status_code == 200


def test_swagger_yaml_accessible(app_basic, client):
    response = client.get("/apispec_1.json")
    assert response.status_code == 200
