from schematics import Model
from schematics.types import DictType, FloatType, IntType, ListType, LongType, ModelType, NumberType, StringType

from apistrap.schematics_converters import schematics_model_to_schema_object


class ExampleModel(Model):
    string = StringType()


def test_schematics_to_schema_object_basic():
    assert schematics_model_to_schema_object(ExampleModel) == {
        'properties': {
            'string': {
                'type': 'string'
            }
        },
        'title': 'ExampleModel',
        'type': 'object'
    }


class ModelWithOptions(Model):
    string = StringType(max_length=10, min_length=3)


def test_schematics_to_schema_object_options():
    assert schematics_model_to_schema_object(ModelWithOptions) == {
        'properties': {
            'string': {
                'maxLength': 10,
                'minLength': 3,
                'type': 'string'
            }
        },
        'title': 'ModelWithOptions',
        'type': 'object'
    }


class NestedModel(Model):
    data = ModelType(ExampleModel)


def test_schematics_to_schema_object_nested_model():
    assert schematics_model_to_schema_object(NestedModel) == {
        'properties': {
            'data': {
                'properties': {
                    'string': {
                        'type': 'string'
                    }
                },
                'title': 'ExampleModel',
                'type': 'object'
            }
        },
        'title': 'NestedModel',
        'type': 'object'
    }


class ModelListModel(Model):
    data = ListType(ModelType(ExampleModel))


def test_schematics_to_schema_object_model_list():
    assert schematics_model_to_schema_object(ModelListModel) == {
        'properties': {
            'data': {
                'items': {
                    'type': 'object',
                    'title': 'ExampleModel',
                    'properties': {
                        'string': {
                            'type': 'string'
                        }
                    }
                },
                'title': 'List of ExampleModel',
                'type': 'array'
            }
        },
        'title': 'ModelListModel',
        'type': 'object'
    }


class PrimitiveListModel(Model):
    data = ListType(IntType)


def test_schematics_to_schema_object_primitive_list():
    assert schematics_model_to_schema_object(PrimitiveListModel) == {
        'properties': {
            'data': {
                'items': {
                    'type': 'integer'
                },
                'title': 'List of IntType',
                'type': 'array'
            }
        },
        'title': 'PrimitiveListModel',
        'type': 'object'
    }


class ModelDictModel(Model):
    data = DictType(ModelType(ExampleModel))


def test_schematics_to_schema_object_model_dict():
    assert schematics_model_to_schema_object(ModelDictModel) == {
        'properties': {
            'data': {
                'additionalProperties': {
                    'type': 'object',
                    'title': 'ExampleModel',
                    'properties': {
                        'string': {
                            'type': 'string'
                        }
                    }
                },
                'title': 'Dictionary of ExampleModel',
                'type': 'object'
            }
        },
        'title': 'ModelDictModel',
        'type': 'object'
    }


class PrimitiveDictModel(Model):
    data = DictType(IntType)


def test_schematics_to_schema_object_primitive_dict():
    assert schematics_model_to_schema_object(PrimitiveDictModel) == {
        'properties': {
            'data': {
                'additionalProperties': {
                    'type': 'integer'
                },
                'title': 'Dictionary of IntType',
                'type': 'object'
            }
        },
        'title': 'PrimitiveDictModel',
        'type': 'object'
    }
