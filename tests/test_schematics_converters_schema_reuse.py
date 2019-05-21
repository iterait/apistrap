import pytest
from schematics import Model
from schematics.types import IntType, ListType, ModelType

from apistrap.flask import FlaskApistrap
from apistrap.schematics_converters import schematics_model_to_schema_object


@pytest.fixture(scope="function")
def apistrap_extension():
    yield FlaskApistrap()


class InnerModel(Model):
    field = IntType()


class ModelWithReuse(Model):
    model_field = ModelType(InnerModel)
    model_list_field = ListType(ModelType(InnerModel))


def test_schema_reuse(apistrap_extension):
    schema = schematics_model_to_schema_object(ModelWithReuse, apistrap_extension)
    assert schema == {
        "$ref": "#/components/schemas/ModelWithReuse"
    }

    definitions = apistrap_extension.to_openapi_dict()["components"]["schemas"]

    assert definitions["ModelWithReuse"] == {
        "type": "object",
        "title": "ModelWithReuse",
        "properties": {
            "model_field": {
                "$ref": "#/components/schemas/InnerModel"
            },
            "model_list_field": {
                "type": "array",
                "title": "List of InnerModel",
                "items": {
                    "$ref": "#/components/schemas/InnerModel"
                }
            }
        }
    }

    assert definitions["InnerModel"] == {
        "type": "object",
        "title": "InnerModel",
        "properties": {
            "field": {
                "type": "integer"
            }
        }
    }
