import pytest
from schematics import Model
from schematics.types import IntType, ListType, ModelType, StringType

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


class NestedModelWithEnums(Model):
    enum_field = StringType(choices=["choice_a", "choice_b"])


class ModelWithEnums(Model):
    enum_field = StringType(choices=["choice_a", "choice_b"])
    nested_field = ModelType(NestedModelWithEnums)


def test_enum_reuse(apistrap_extension):
    schema = schematics_model_to_schema_object(ModelWithEnums, apistrap_extension)
    assert schema == {
        "$ref": "#/components/schemas/ModelWithEnums"
    }

    definitions = apistrap_extension.to_openapi_dict()["components"]["schemas"]

    assert definitions["EnumField"] == {
        "type": "string",
        "enum": ["choice_a", "choice_b"]
    }

    assert definitions["ModelWithEnums"] == {
        "type": "object",
        "title": "ModelWithEnums",
        "properties": {
            "enum_field": {
                "$ref": "#/components/schemas/EnumField"
            },
            "nested_field": {
                "$ref": "#/components/schemas/NestedModelWithEnums"
            }
        }
    }

    assert definitions["NestedModelWithEnums"] == {
        "type": "object",
        "title": "NestedModelWithEnums",
        "properties": {
            "enum_field": {
                "$ref": "#/components/schemas/EnumField"
            },
        }
    }
