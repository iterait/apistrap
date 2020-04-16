import pytest
from schematics import Model
from schematics.types import FloatType, StringType, UnionType

from apistrap.flask import FlaskApistrap
from apistrap.schematics_converters import schematics_model_to_schema_object
from apistrap.types import DiscriminatedModelType


@pytest.fixture(scope="function")
def apistrap_extension():
    yield FlaskApistrap()


class VariantA(Model):
    type = StringType(required=True)
    string_field = StringType()


class VariantB(Model):
    type = StringType(required=True)
    number_field = FloatType(required=True)


class ModelWithDiscriminatedModel(Model):
    model_field = DiscriminatedModelType("TwoVariantModel", "type", {"a": VariantA, "b": VariantB})


def test_discriminated_models(apistrap_extension):
    result = schematics_model_to_schema_object(ModelWithDiscriminatedModel, apistrap_extension)
    assert result == {"$ref": "#/components/schemas/ModelWithDiscriminatedModel"}

    definitions = apistrap_extension.to_openapi_dict()["components"]["schemas"]

    assert definitions["ModelWithDiscriminatedModel"] == {
        "title": "ModelWithDiscriminatedModel",
        "type": "object",
        "properties": {"model_field": {"$ref": "#/components/schemas/TwoVariantModel"},},
    }

    assert definitions["TwoVariantModel"] == {
        "anyOf": [{"$ref": "#/components/schemas/VariantA"}, {"$ref": "#/components/schemas/VariantB"},],
        "discriminator": {
            "propertyName": "type",
            "mapping": {
                "a": "#/components/schemas/VariantA",
                "b": "#/components/schemas/VariantB"
            }
        },
    }
