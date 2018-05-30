from typing import Type, Generator, Dict, Any

from schematics import Model
from schematics.types.base import (BaseType, NumberType, IntType, LongType, FloatType,
                                   DecimalType, BooleanType)
from schematics.types.compound import ModelType, ListType, DictType


def _get_serialized_name(field: BaseType) -> str:
    """
    Get the name under which the model field is saved in the serialized object

    :param field: the model field
    :return: a field name
    """
    return getattr(field, 'serialized_name', None) or field.name


def _model_fields_to_schema_object_properties(model: Type[Model]) -> Dict[str, Any]:
    """
    Convert all fields of a model to OpenAPI 2 SchemaObject Properties objects

    :param model: the model to be converted
    :return: a dictionary with field names as keys and SchemaObjects as values
    """
    properties = {}

    for field in model._fields.values():
        serialized_name = _get_serialized_name(field)

        if isinstance(field, ModelType):
            properties[serialized_name] = schematics_model_to_schema_object(field.model_class)
        elif isinstance(field, ListType):
            if isinstance(field.field, ModelType):
                properties[serialized_name] = _model_array_to_schema_object(field.field.model_class)
            elif isinstance(field.field, BaseType):
                properties[serialized_name] = _primitive_array_to_schema_object(field.field)
        elif isinstance(field, DictType):
            if isinstance(field.field, ModelType):
                properties[serialized_name] = _model_dict_to_schema_object(field.field.model_class)
            elif isinstance(field.field, BaseType):
                properties[serialized_name] = _primitive_dict_to_schema_object(field.field)
        elif isinstance(field, BaseType):
            properties[serialized_name] = _primitive_field_to_schema_object(field)

    return properties


SCHEMATICS_TYPE_TO_JSON_TYPE = {
    NumberType: 'number',
    IntType: 'integer',
    LongType: 'integer',
    FloatType: 'number',
    DecimalType: 'number',
    BooleanType: 'boolean',
}

SCHEMATICS_OPTIONS_TO_JSON_SCHEMA = {
    'max_length': 'maxLength',
    'min_length': 'minLength',
    'regex': 'pattern',
    'min_value': 'minimum',
    'max_value': 'maximum',
}


def _primitive_field_to_schema_object(field: BaseType) -> Dict[str, str]:
    schema = {
        "type": SCHEMATICS_TYPE_TO_JSON_TYPE.get(field.__class__, 'string')
    }

    for schematics_attr, json_schema_attr in SCHEMATICS_OPTIONS_TO_JSON_SCHEMA.items():
        if hasattr(field, schematics_attr):
            option_value = getattr(field, schematics_attr)
            if option_value is not None:
                schema[json_schema_attr] = option_value

    return schema


def _get_required_fields(model: Type[Model]) -> Generator[str, None, None]:
    """
    Extract required field names from a Schematics model

    :param model:
    :return: a generator of field names
    """

    for field in model._fields.values():
        if getattr(field, 'required', False):
            yield _get_serialized_name(field)


def _model_array_to_schema_object(model: Type[Model]) -> Dict[str, Any]:
    """
    Get a SchemaObject for a list of given models

    :param model: the model to be converted
    :return: a SchemaObject
    """
    return {
        'type': 'array',
        'title': 'List of {}'.format(model.__name__),
        'items': schematics_model_to_schema_object(model),
    }


def _model_dict_to_schema_object(model: Type[Model]) -> Dict[str, Any]:
    """
    Get a SchemaObject for a dictionary of given models

    :param model: the model to be converted
    :return: a SchemaObject
    """
    return {
        'type': 'object',
        'title': 'Dictionary of {}'.format(model.__name__),
        'additionalProperties': schematics_model_to_schema_object(model)
    }


def _primitive_array_to_schema_object(field: BaseType) -> Dict[str, Any]:
    """
    Get a SchemaObject for a list of primitive types
    :param field: the field that determines the value type
    :return: a SchemaObject
    """
    return {
        'type': 'array',
        'title': 'List of {}'.format(field.__class__.__name__),
        'items': _primitive_field_to_schema_object(field)
    }


def _primitive_dict_to_schema_object(field: BaseType) -> Dict[str, Any]:
    """
    Get a SchemaObject for a dictionary of primitive types

    :param field: the field that determines the value type
    :return: a SchemaObject
    """
    return {
        'type': 'object',
        'title': 'Dictionary of {}'.format(field.__class__.__name__),
        'additionalProperties': _primitive_field_to_schema_object(field)
    }


def schematics_model_to_schema_object(model: Type[Model]) -> Dict[str, Any]:
    """
    Convert a Schematics model to an OpenAPI 2 SchemaObject

    :param model: the model to be converted
    :return: a SchemaObject
    """
    schema = {
        'type': 'object',
        'title': model.__name__,
        'properties': (_model_fields_to_schema_object_properties(model)),
    }

    required = list(_get_required_fields(model))

    if required:
        schema['required'] = required

    return schema
