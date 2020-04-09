from schematics import Model
from schematics.types import DictType, FloatType, IntType, ListType, ModelType, StringType, UnionType

from apistrap.schematics_converters import schematics_model_to_schema_object


class ExampleModel(Model):
    string = StringType()


def test_schematics_to_schema_object_basic():
    assert schematics_model_to_schema_object(ExampleModel) == {
        "properties": {"string": {"type": "string"}},
        "title": "ExampleModel",
        "type": "object",
    }


class ModelWithOptions(Model):
    string = StringType(max_length=10, min_length=3)


def test_schematics_to_schema_object_options():
    assert schematics_model_to_schema_object(ModelWithOptions) == {
        "properties": {"string": {"maxLength": 10, "minLength": 3, "type": "string"}},
        "title": "ModelWithOptions",
        "type": "object",
    }


class NestedModel(Model):
    data = ModelType(ExampleModel)


def test_schematics_to_schema_object_nested_model():
    assert schematics_model_to_schema_object(NestedModel) == {
        "properties": {
            "data": {"properties": {"string": {"type": "string"}}, "title": "ExampleModel", "type": "object"}
        },
        "title": "NestedModel",
        "type": "object",
    }


class ModelListModel(Model):
    data = ListType(ModelType(ExampleModel))


def test_schematics_to_schema_object_model_list():
    assert schematics_model_to_schema_object(ModelListModel) == {
        "properties": {
            "data": {
                "items": {"type": "object", "title": "ExampleModel", "properties": {"string": {"type": "string"}}},
                "title": "List of ExampleModel",
                "type": "array",
            }
        },
        "title": "ModelListModel",
        "type": "object",
    }


class PrimitiveListModel(Model):
    data = ListType(IntType)


def test_schematics_to_schema_object_primitive_list():
    assert schematics_model_to_schema_object(PrimitiveListModel) == {
        "properties": {"data": {"items": {"type": "integer"}, "title": "List of IntType", "type": "array"}},
        "title": "PrimitiveListModel",
        "type": "object",
    }


class ModelDictModel(Model):
    data = DictType(ModelType(ExampleModel))


def test_schematics_to_schema_object_model_dict():
    assert schematics_model_to_schema_object(ModelDictModel) == {
        "properties": {
            "data": {
                "additionalProperties": {
                    "type": "object",
                    "title": "ExampleModel",
                    "properties": {"string": {"type": "string"}},
                },
                "title": "Dictionary of ExampleModel",
                "type": "object",
            }
        },
        "title": "ModelDictModel",
        "type": "object",
    }


class PrimitiveDictModel(Model):
    data = DictType(IntType)


def test_schematics_to_schema_object_primitive_dict():
    assert schematics_model_to_schema_object(PrimitiveDictModel) == {
        "properties": {
            "data": {"additionalProperties": {"type": "integer"}, "title": "Dictionary of IntType", "type": "object"}
        },
        "title": "PrimitiveDictModel",
        "type": "object",
    }


class NestedDictModel(Model):
    data = DictType(DictType(StringType))


def test_schematics_to_schema_object_nested_dict():
    assert schematics_model_to_schema_object(NestedDictModel) == {
        "properties": {
            "data": {
                "additionalProperties": {
                    "type": "object",
                    "title": "Dictionary of StringType",
                    "additionalProperties": {"type": "string"},
                },
                "title": "Dictionary of DictType",
                "type": "object",
            }
        },
        "title": "NestedDictModel",
        "type": "object",
    }


class ModelWithDescriptions(Model):
    primitive = IntType(metadata={"label": "Primitive title", "description": "Primitive description"})
    list = ListType(StringType(), metadata={"label": "List title", "description": "List description"})
    dict = DictType(StringType(), metadata={"label": "Dict title", "description": "Dict description"})
    model = ModelType(ExampleModel, metadata={"label": "Model title", "description": "Model description"})


def test_schematics_to_schema_object_descriptions():
    assert schematics_model_to_schema_object(ModelWithDescriptions) == {
        "properties": {
            "primitive": {"type": "integer", "title": "Primitive title", "description": "Primitive description",},
            "list": {
                "type": "array",
                "items": {"type": "string"},
                "title": "List title",
                "description": "List description",
            },
            "dict": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "title": "Dict title",
                "description": "Dict description",
            },
            "model": {
                "type": "object",
                "title": "Model title",
                "description": "Model description",
                "properties": {"string": {"type": "string"}},
            },
        },
        "title": "ModelWithDescriptions",
        "type": "object",
    }


class ModelWithEnum(Model):
    enum_field = StringType(choices=["member_a", "member_b"])


def test_enum():
    assert schematics_model_to_schema_object(ModelWithEnum) == {
        "title": "ModelWithEnum",
        "type": "object",
        "properties": {"enum_field": {"type": "string", "enum": ["member_a", "member_b"]}},
    }


class ModelWithUnions(Model):
    number_field = UnionType([IntType, FloatType])
    string_field = UnionType([StringType, StringType])


def test_unions():
    assert schematics_model_to_schema_object(ModelWithUnions) == {
        "title": "ModelWithUnions",
        "type": "object",
        "properties": {
            "number_field": {"oneOf": [{"type": "integer"}, {"type": "number"}]},
            "string_field": {"type": "string"},
        },
    }
