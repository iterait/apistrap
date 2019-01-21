import pytest
from flask import jsonify

from schematics import Model
from schematics.types import IntType


def extract_definition_name(definition_spec: str):
    return definition_spec.split("/")[-1]


class CustomType(IntType):
    pass


class RequestModel(Model):
    field = CustomType(required=True)


@pytest.fixture()
def app_with_accepts(app, swagger):
    @app.route("/", methods=["POST"])
    @swagger.autodoc()
    @swagger.accepts(RequestModel)
    def view(req: RequestModel):
        return jsonify()


def test_int_subtype(client, app_with_accepts):
    spec = client.get("/swagger.json").json
    path = spec["paths"]["/"]["post"]
    body = next(filter(lambda item: item["in"] == "body", path["parameters"]), None)
    assert body is not None

    ref = extract_definition_name(body["schema"]["$ref"])
    assert spec["definitions"][ref] == {
        "title": RequestModel.__name__,
        "type": "object",
        "properties": {
            "field": {
                "type": "integer"
            }
        },
        "required": ["field"]
    }
