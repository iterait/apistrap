import pytest
from schematics import Model

from apistrap.flask import FlaskApistrap
from apistrap.schematics_converters import schematics_model_to_schema_object
from apistrap.types import AnyType


@pytest.fixture(scope="function")
def apistrap_extension():
    yield FlaskApistrap()


class ModelWithAny(Model):
    any_field = AnyType()


def test_any(apistrap_extension):
    result = schematics_model_to_schema_object(ModelWithAny, apistrap_extension)
    assert result == {"$ref": "#/components/schemas/ModelWithAny"}

    definitions = apistrap_extension.to_openapi_dict()["components"]["schemas"]
    assert definitions["ModelWithAny"] == {"title": "ModelWithAny", "type": "object", "properties": {"any_field": {}}}
