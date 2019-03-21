import pytest
from flask import jsonify


@pytest.fixture()
def app_basic(app, flask_apistrap):
    @app.route("/")
    def view():
        return jsonify()

    @app.route("/view/<param>/<typed_param>")
    def view_with_params(param, typed_param: int):
        return jsonify()


def test_ui_accessible(app_basic, client):
    response = client.get("/apidocs")
    assert response.status_code == 200


def test_ui_accessible_1(app_basic, client):
    response = client.get("/apidocs/")
    assert response.status_code == 200


def test_spec_json_accessible(app_basic, client):
    response = client.get("/spec.json")
    assert response.status_code == 200


def test_endpoint_present_in_spec_json(app_basic, client):
    response = client.get("/spec.json")
    assert "/" in response.json["paths"].keys()


def test_path_params_present_in_spec_json(app_basic, client):
    response = client.get("/spec.json")
    path = "/view/{param}/{typed_param}"

    assert path in response.json["paths"].keys()
    assert response.json["paths"][path]["get"]["parameters"] == [
        {
            "in": "path",
            "name": "param",
            "required": True,
            "schema": {
                "type": "string",
            },
        }, {
            "in": "path",
            "name": "typed_param",
            "schema": {
                "type": "integer",
            },
            "required": True
        }
    ]


def test_operation_id_present_in_spec_json(app_basic, client):
    response = client.get("/spec.json")
    path = "/view/{param}/{typed_param}"
    assert path in response.json["paths"].keys()
    assert response.json["paths"][path]["get"]["operationId"] == "viewWithParams"
