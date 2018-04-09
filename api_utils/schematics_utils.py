from typing import Type

from schematics import Model
from schematics.types.base import (BaseType, NumberType, IntType, LongType, FloatType,
                                   DecimalType, BooleanType)
from schematics.types.compound import ModelType, ListType

__version__ = '1.0'


SCHEMATIC_TYPE_TO_JSON_TYPE = {
    NumberType: 'number',
    IntType: 'integer',
    LongType: 'integer',
    FloatType: 'number',
    DecimalType: 'number',
    BooleanType: 'boolean',
}

# Schema Serialization

# Parameters for serialization to JSONSchema
schema_kwargs_to_schematics = {
    'maxLength': 'max_length',
    'minLength': 'min_length',
    'pattern': 'regex',
    'minimum': 'min_value',
    'maximum': 'max_value',
}


def schema_object_for_fields(model: Type[Model]):
    properties = {}
    required = []
    # Loop over each field and either evict it or convert it
    for field_name, field_instance in model._fields.items():
        # Break 3-tuple out
        print (field_name, field_instance)
        serialized_name = getattr(field_instance, 'serialized_name', None) or field_name

        if isinstance(field_instance, ModelType):
            properties[serialized_name] = schema_object_for_model(field_instance.model_class)

        elif isinstance(field_instance, ListType):
            properties[serialized_name] = schema_object_for_model(field_instance.model_class, 'array')

        # Convert field as single model
        elif isinstance(field_instance, BaseType):
            properties[serialized_name] = {
                "type": SCHEMATIC_TYPE_TO_JSON_TYPE.get(field_instance.__class__, 'string')
            }

        if getattr(field_instance, 'required', False):
            required.append(serialized_name)

    return properties, required


def schema_object_for_model(model: Type[Model], _type='object'):

    properties, required = schema_object_for_fields(model)

    schema = {
        'type': _type,
        'title': model.__name__,
        'properties': properties,
    }

    if required:
        schema['required'] = required

    if _type == 'array':
        schema = {
            'type': 'array',
            'title': 'List of {}'.format(model.__name__),
            'items': schema,
        }

    return schema
