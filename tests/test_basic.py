import pytest
from flask import jsonify


@pytest.fixture()
def app_basic(app, swagger):
    @app.route("/")
    @swagger.autodoc()
    def view():
        return jsonify()

    @app.route("/view/<param>/<typed_param>")
    @swagger.autodoc()
    def view_with_params(param, typed_param: int):
        return jsonify()


def test_ui_accessible(app_basic, client):
    response = client.get("/apidocs/")
    assert response.status_code == 200


def test_swagger_json_accessible(app_basic, client):
    response = client.get("/swagger.json")
    assert response.status_code == 200


def test_endpoint_present_in_swagger_json(app_basic, client):
    response = client.get("/swagger.json")
    assert "/" in response.json["paths"].keys()


def test_path_params_present_in_swagger_json(app_basic, client):
    response = client.get("/swagger.json")
    path = "/view/{param}/{typed_param}"

    assert path in response.json["paths"].keys()
    assert response.json["paths"][path]["get"]["parameters"] == [
        {
            "in": "path",
            "name": "param"
        }, {
            "in": "path",
            "name": "typed_param",
            "type": "integer"
        }
    ]

def test_operation_id_present_in_swagger_json(app_basic, client):
    response = client.get("/swagger.json")
    path = "/view/{param}/{typed_param}"
    assert path in response.json["paths"].keys()
    assert response.json["paths"][path]["get"]["operationId"] == "viewWithParams"
