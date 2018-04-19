import pytest
from api_utils import Swagger


def test_swagger_extension_definition_conflict():
    with pytest.raises(ValueError):
        swagger = Swagger()
        swagger.add_definition("name", {"foo": "bar"})
        swagger.add_definition("name", {"baz": "bar"})
