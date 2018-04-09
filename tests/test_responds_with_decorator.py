import pytest
from schematics import Model
from schematics.types import StringType


def extract_definition_name(definition_spec: str):
    return definition_spec.split("/")[-1]


class OkResponse(Model):
    string_field = StringType()


class ErrorResponse(Model):
    error_message = StringType()


@pytest.fixture()
def app_with_responds_with(app, swagger):
    @app.route("/")
    @swagger.autodoc()
    @swagger.responds_with(OkResponse)
    @swagger.responds_with(ErrorResponse, code=400)
    def view():
        return OkResponse(dict(string_field="Hello World"))


def test_responses_in_swagger_json(app_with_responds_with, client):
    response = client.get("/apispec_1.json")

    assert "definitions" in response.json

    assert "200" in response.json["paths"]["/"]["get"]["responses"]
    assert "$ref" in response.json["paths"]["/"]["get"]["responses"]["200"]
    ref = extract_definition_name(response.json["paths"]["/"]["get"]["responses"]["200"]["$ref"])

    assert response.json["definitions"][ref] == {
        "title": "OkResponse",
        "type": "object",
        "properties": {
            "string_field": {
                "type": "string"
            }
        }
    }

    assert "400" in response.json["paths"]["/"]["get"]["responses"]
    assert "$ref" in response.json["paths"]["/"]["get"]["responses"]["400"]
    ref = extract_definition_name(response.json["paths"]["/"]["get"]["responses"]["400"]["$ref"])

    assert response.json["definitions"][ref] == {
        "title": "ErrorResponse",
        "type": "object",
        "properties": {
            "error_message": {
                "type": "string"
            }
        }
    }
