import pytest
from schematics import Model
from schematics.types import FloatType, IntType, StringType, UnionType

from apistrap.flask import FlaskApistrap
from apistrap.schematics_converters import schematics_model_to_schema_object


@pytest.fixture(scope="function")
def apistrap_extension():
    yield FlaskApistrap()


class ModelWithUnions(Model):
    number_field = UnionType([IntType, FloatType])
    string_field = UnionType([StringType, StringType])


def test_unions(apistrap_extension):
    result = schematics_model_to_schema_object(ModelWithUnions, apistrap_extension)
    assert result == {
        "$ref": "#/components/schemas/ModelWithUnions"
    }

    definitions = apistrap_extension.to_openapi_dict()["components"]["schemas"]

    assert definitions["ModelWithUnions"] == {
        "title": "ModelWithUnions",
        "type": "object",
        "properties": {
            "number_field": {"$ref": "#/components/schemas/NumberFieldUnion"},
            "string_field": {"type": "string"},
        },
    }

    assert definitions["NumberFieldUnion"] == {
        "anyOf": [{"type": "integer"}, {"type": "number"}]
    }
