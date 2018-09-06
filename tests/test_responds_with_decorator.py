import io
import pytest
from schematics import Model
from schematics.types import StringType

from apistrap.errors import UnexpectedResponseError, InvalidResponseError
from apistrap.types import FileResponse

def extract_definition_name(definition_spec: str):
    return definition_spec.split("/")[-1]


class OkResponse(Model):
    string_field = StringType(required=True)


class WeirdResponse(Model):
    string_field = StringType(required=True)


class ErrorResponse(Model):
    error_message = StringType(required=True)


@pytest.fixture()
def app_with_responds_with(app, swagger):
    @app.route("/")
    @swagger.autodoc()
    @swagger.responds_with(OkResponse)
    @swagger.responds_with(ErrorResponse, code=400)
    def view():
        return OkResponse(dict(string_field="Hello World"))

    @app.route("/description")
    @swagger.autodoc()
    @swagger.responds_with(OkResponse, description='my description')
    def descriptive_view():
        return OkResponse(dict(string_field="Hello descriptive World"))

    @app.route("/error")
    @swagger.autodoc()
    @swagger.responds_with(OkResponse)
    @swagger.responds_with(ErrorResponse, code=400)
    def error_view():
        return ErrorResponse(dict(error_message="Error"))

    @app.route("/weird")
    @swagger.autodoc()
    @swagger.responds_with(OkResponse)
    @swagger.responds_with(ErrorResponse, code=400)
    def weird_view():
        return WeirdResponse(dict(string_field="Hello World"))

    @app.route("/invalid")
    @swagger.autodoc()
    @swagger.responds_with(OkResponse)
    @swagger.responds_with(ErrorResponse, code=400)
    def invalid_view():
        return OkResponse(dict())

    @app.route("/file")
    @swagger.autodoc()
    @swagger.responds_with(FileResponse)
    def get_file():
        message = 'hello'
        return FileResponse(filename_or_fp=io.BytesIO(message.encode('UTF-8')),
                            as_attachment=True,
                            attachment_filename='hello.txt')


def test_responses_in_swagger_json(app_with_responds_with, client):
    response = client.get("/swagger.json")

    assert "definitions" in response.json

    # test ok response
    assert "200" in response.json["paths"]["/"]["get"]["responses"]
    assert "schema" in response.json["paths"]["/"]["get"]["responses"]["200"]
    assert "$ref" in response.json["paths"]["/"]["get"]["responses"]["200"]["schema"]
    ref = extract_definition_name(response.json["paths"]["/"]["get"]["responses"]["200"]["schema"]["$ref"])

    assert response.json["definitions"][ref] == {
        "title": "OkResponse",
        "type": "object",
        "properties": {
            "string_field": {
                "type": "string"
            }
        },
        "required": ["string_field"]
    }

    # test default and custom descriptions
    assert "description" in response.json["paths"]["/"]["get"]["responses"]["200"]
    assert "OkResponse" == response.json["paths"]["/"]["get"]["responses"]["200"]["description"]
    assert "description" in response.json["paths"]["/description"]["get"]["responses"]["200"]
    assert "my description" == response.json["paths"]["/description"]["get"]["responses"]["200"]["description"]

    # test error response
    assert "400" in response.json["paths"]["/"]["get"]["responses"]
    assert "schema" in response.json["paths"]["/"]["get"]["responses"]["400"]
    assert "$ref" in response.json["paths"]["/"]["get"]["responses"]["400"]["schema"]
    ref = extract_definition_name(response.json["paths"]["/"]["get"]["responses"]["400"]["schema"]["$ref"])

    assert response.json["definitions"][ref] == {
        "title": "ErrorResponse",
        "type": "object",
        "properties": {
            "error_message": {
                "type": "string"
            }
        },
        "required": ["error_message"]
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
    print(response.json)
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
    assert response.data == b'hello'
