import json

import pytest
from flask import jsonify
from schematics import Model
from schematics.types import StringType, IntType
from werkzeug.test import Client

from api_utils.errors import ApiClientError, InvalidFieldsError


def extract_definition_name(definition_spec: str):
    return definition_spec.split("/")[-1]


class Request(Model):
    string_field: str = StringType(required=True)
    int_field: int = IntType(required=True)


@pytest.fixture()
def app_with_accepts(app, swagger):
    @app.route("/", methods=["POST"])
    @swagger.autodoc()
    @swagger.accepts(Request)
    def view(req: Request):
        assert req.string_field == "foo"
        assert req.int_field == 42
        return jsonify()


def test_parameters_in_swagger_json(app_with_accepts, client):
    response = client.get("/apispec_1.json")

    assert "definitions" in response.json

    path = response.json["paths"]["/"]["post"]
    assert "parameters" in path

    body = next(filter(lambda item: item["in"] == "body", path["parameters"]), None)
    assert body is not None
    assert body["required"] is True

    ref = extract_definition_name(body["schema"]["$ref"])
    assert response.json["definitions"][ref] == {
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
def app_with_arg(app, swagger):
    @app.route("/<arg>", methods=["POST"])
    @swagger.autodoc()
    @swagger.accepts(Request)
    def view(arg, req: Request):
        assert req.string_field == "foo"
        assert req.int_field == 42
        return jsonify()


def test_correct_parameters(app_with_arg, client: Client):
    response = client.get("/apispec_1.json")
    path = response.json["paths"]["/{arg}"]["post"]
    assert len(path["parameters"]) == 2
    assert next(filter(lambda item: item["in"] == "body", path["parameters"]), None) is not None
    assert next(filter(lambda item: item["in"] == "path", path["parameters"]), None) is not None


def test_no_injection_parameter(app, swagger):
    """
    If the `accepts` decorator is applied to a function that has no parameter with a type annotation corresponding to
    the request type, an exception should be thrown.
    """

    def view():
        return jsonify()

    with pytest.raises(TypeError):
        swagger.accepts(Request)(view)
