import io

import pytest
from pydantic import BaseModel

from apistrap.errors import InvalidResponseError, UnexpectedResponseError
from apistrap.schemas import EmptyResponse
from apistrap.types import FileResponse


def extract_definition_name(definition_spec: str):
    return definition_spec.split("/")[-1]


class OkResponse(BaseModel):
    string_field: str


class WeirdResponse(BaseModel):
    string_field: str


class ErrorResponse(BaseModel):
    error_message: str


@pytest.fixture()
def app_with_responds_with(app, flask_apistrap):
    @app.route("/")
    @flask_apistrap.responds_with(OkResponse)
    @flask_apistrap.responds_with(ErrorResponse, code=400)
    def view():
        return OkResponse(string_field="Hello World")

    @app.route("/description")
    @flask_apistrap.responds_with(OkResponse, description="my description")
    def descriptive_view():
        return OkResponse(string_field="Hello descriptive World")

    @app.route("/error")
    @flask_apistrap.responds_with(OkResponse)
    @flask_apistrap.responds_with(ErrorResponse, code=400)
    def error_view():
        return ErrorResponse(error_message="Error")

    @app.route("/weird")
    @flask_apistrap.responds_with(OkResponse)
    @flask_apistrap.responds_with(ErrorResponse, code=400)
    def weird_view():
        return WeirdResponse(string_field="Hello World")

    @app.route("/invalid")
    @flask_apistrap.responds_with(OkResponse)
    @flask_apistrap.responds_with(ErrorResponse, code=400)
    def invalid_view():
        return OkResponse()

    @app.route("/file")
    @flask_apistrap.responds_with(FileResponse)
    def get_file():
        message = "hello"
        return FileResponse(
            filename_or_fp=io.BytesIO(message.encode("UTF-8")), as_attachment=True, attachment_filename="hello.txt"
        )

    @app.route("/empty")
    @flask_apistrap.responds_with(EmptyResponse)
    def get_empty_response():
        return EmptyResponse()

    @app.route("/multiple")
    @flask_apistrap.responds_with(EmptyResponse, code=200)
    @flask_apistrap.responds_with(EmptyResponse, code=201)
    def get_multiple_responses():
        return EmptyResponse(), 201

    @app.route("/multiple_missing_code")
    @flask_apistrap.responds_with(EmptyResponse, code=200)
    @flask_apistrap.responds_with(EmptyResponse, code=201)
    def get_multiple_responses_missing_code():
        return EmptyResponse()

    @app.route("/unexpected_code")
    @flask_apistrap.responds_with(EmptyResponse, code=200)
    @flask_apistrap.responds_with(EmptyResponse, code=201)
    def get_multiple_responses_unexpected_code():
        return EmptyResponse(), 300


def test_responses_in_spec_json(app_with_responds_with, client):
    response = client.get("/spec.json")

    assert "components" in response.json

    # test ok response
    assert "200" in response.json["paths"]["/"]["get"]["responses"]
    assert "schema" in response.json["paths"]["/"]["get"]["responses"]["200"]["content"]["application/json"]
    assert "$ref" in response.json["paths"]["/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    ref = extract_definition_name(
        response.json["paths"]["/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    )

    assert response.json["components"]["schemas"][ref] == {
        "title": "OkResponse",
        "type": "object",
        "properties": {"string_field": {"type": "string", "title": "String Field"}},
        "required": ["string_field"],
    }

    # test default and custom descriptions
    assert "description" in response.json["paths"]["/"]["get"]["responses"]["200"]
    assert "OkResponse" == response.json["paths"]["/"]["get"]["responses"]["200"]["description"]
    assert "description" in response.json["paths"]["/description"]["get"]["responses"]["200"]
    assert "my description" == response.json["paths"]["/description"]["get"]["responses"]["200"]["description"]

    # test error response
    assert "400" in response.json["paths"]["/"]["get"]["responses"]
    assert "schema" in response.json["paths"]["/"]["get"]["responses"]["400"]["content"]["application/json"]
    assert "$ref" in response.json["paths"]["/"]["get"]["responses"]["400"]["content"]["application/json"]["schema"]
    ref = extract_definition_name(
        response.json["paths"]["/"]["get"]["responses"]["400"]["content"]["application/json"]["schema"]["$ref"]
    )

    assert response.json["components"]["schemas"][ref] == {
        "title": "ErrorResponse",
        "type": "object",
        "properties": {"error_message": {"type": "string", "title": "Error Message"}},
        "required": ["error_message"],
    }


def test_ok_response(app_with_responds_with, client):
    response = client.get("/")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json["string_field"] == "Hello World"


def test_error_response(app_with_responds_with, client):
    response = client.get("/error")
    assert response.status_code == 400
    assert len(response.json) == 1
    assert response.json["error_message"] == "Error"


def test_weird_response(app_with_responds_with, client, propagate_exceptions):
    with pytest.raises(UnexpectedResponseError):
        client.get("/weird")


def test_invalid_response(app_with_responds_with, client, propagate_exceptions):
    with pytest.raises(InvalidResponseError):
        client.get("/invalid")


def test_file_response(app_with_responds_with, client):
    response = client.get("/file")
    assert response.status_code == 200
    assert response.data == b"hello"


def test_empty_response(app_with_responds_with, client):
    response = client.get("/empty")
    assert response.status_code == 200
    assert response.json == {}


def test_multiple_responses(app_with_responds_with, client):
    response = client.get("/multiple")
    assert response.status_code == 201
    assert response.json == {}


def test_multiple_responses_missing_code(app_with_responds_with, client, propagate_exceptions):
    with pytest.raises(InvalidResponseError):
        client.get("/multiple_missing_code")


def test_multiple_responses_unexpected_code(app_with_responds_with, client, propagate_exceptions):
    with pytest.raises(UnexpectedResponseError):
        client.get("/unexpected_code")
