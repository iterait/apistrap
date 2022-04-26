import pytest
from flask import jsonify
from pydantic import BaseModel


def extract_definition_name(definition_spec: str):
    return definition_spec.split("/")[-1]


class CustomType(int):
    pass


class RequestModel(BaseModel):
    field: CustomType


@pytest.fixture()
def app_with_accepts(app, flask_apistrap):
    @app.route("/", methods=["POST"])
    @flask_apistrap.accepts(RequestModel)
    def view(req: RequestModel):
        return jsonify()


def test_int_subtype(client, app_with_accepts):
    spec = client.get("/spec.json").json
    path = spec["paths"]["/"]["post"]
    body = path["requestBody"]
    assert body is not None
    assert body["required"]

    ref = extract_definition_name(body["content"]["application/json"]["schema"]["$ref"])
    assert spec["components"]["schemas"][ref] == {
        "title": "RequestModel",
        "type": "object",
        "properties": {"field": {"type": "integer", "title": "Field"}},
        "required": ["field"],
    }
