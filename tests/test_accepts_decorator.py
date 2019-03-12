import json

import pytest
from flask import jsonify
from schematics import Model
from schematics.types import StringType, IntType
from werkzeug.test import Client

from apistrap.errors import ApiClientError, InvalidFieldsError


def extract_definition_name(definition_spec: str):
    return definition_spec.split("/")[-1]


class Request(Model):
    string_field: str = StringType(required=True)
    int_field: int = IntType(required=True)


@pytest.fixture()
def app_with_accepts(app, flask_apistrap):
    @app.route("/", methods=["POST"])
    @flask_apistrap.accepts(Request)
    def view(req: Request):
        assert req.string_field == "foo"
        assert req.int_field == 42
        return jsonify()


def test_parameters_in_swagger_json(app_with_accepts, client):
    response = client.get("/swagger.json")

    assert "components" in response.json
    assert "schemas" in response.json["components"]

    path = response.json["paths"]["/"]["post"]
    assert "parameters" in path

    body = path["requestBody"]
    assert body is not None
    assert body["required"] is True

    ref = extract_definition_name(body["content"]["application/json"]["schema"]["$ref"])
    assert response.json["components"]["schemas"][ref] == {
        "title": Request.__name__,
        "type": "object",
        "properties": {
            "int_field": {
                "type": "integer"
            },
            "string_field": {
                "type": "string"
            }
        },
        "required": ["string_field", "int_field"]
    }


def test_request_parsing(app_with_accepts, client: Client):
    response = client.post("/", content_type="application/json", data=json.dumps({
        "string_field": "foo",
        "int_field": 42
    }))

    assert response.status_code == 200


def test_unsupported_content_type(app_with_accepts, client: Client, propagate_exceptions):
    with pytest.raises(ApiClientError):
        client.post("/", data=json.dumps({
            "string_field": "foo",
            "int_field": 42
        }))


@pytest.mark.parametrize("field", ["string_field", "int_field"])
def test_missing_field(app_with_accepts, client: Client, field, propagate_exceptions):
    with pytest.raises(InvalidFieldsError):
        req_data = {"string_field": "foo", "int_field": 42}
        del req_data[field]
        client.post("/", content_type="application/json", data=json.dumps(req_data))


def test_unexpected_field(app_with_accepts, client: Client, propagate_exceptions):
    with pytest.raises(InvalidFieldsError):
        client.post("/", content_type="application/json", data=json.dumps({
            "string_field": "foo",
            "int_field": 42,
            "unexpected_field": "Spanish inquisition"
        }))


def test_invalid_field(app_with_accepts, client: Client, propagate_exceptions):
    with pytest.raises(InvalidFieldsError):
        client.post("/", content_type="application/json", data=json.dumps({
            "string_field": "foo",
            "int_field": "Hello"
        }))


@pytest.fixture()
def app_with_arg(app, flask_apistrap):
    @app.route("/<arg>", methods=["POST"])
    @flask_apistrap.accepts(Request)
    def view(arg, req: Request):
        assert req.string_field == "foo"
        assert req.int_field == 42
        return jsonify()


def test_correct_parameters(app_with_arg, client: Client):
    response = client.get("/swagger.json")
    path = response.json["paths"]["/{arg}"]["post"]

    assert len(path["parameters"]) == 1
    assert path["parameters"][0]["in"] == "path"

    assert path["requestBody"] is not None


def test_no_injection_parameter(app, flask_apistrap):
    """
    If the `accepts` decorator is applied to a function that has no parameter with a type annotation corresponding to
    the request type, an exception should be thrown.
    """

    def view():
        return jsonify()

    with pytest.raises(TypeError):
        flask_apistrap.accepts(Request)(view)
