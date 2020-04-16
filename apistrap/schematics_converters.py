from __future__ import annotations

from inspect import getmro
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional, Type

from schematics import Model
from schematics.types import UnionType
from schematics.types.base import (
    BaseType,
    BooleanType,
    DecimalType,
    FloatType,
    IntType,
    LongType,
    NumberType,
    StringType,
)
from schematics.types.compound import DictType, ListType, ModelType, PolyModelType

from apistrap.types import AnyType, DiscriminatedModelType
from apistrap.utils import snake_to_camel

if TYPE_CHECKING:  # pragma: no cover
    from apistrap.extension import Apistrap


def _get_serialized_name(field: BaseType) -> str:
    """
    Get the name under which the model field is saved in the serialized object

    :param field: the model field
    :return: a field name
    """
    return getattr(field, "serialized_name", None) or field.name


def _model_fields_to_schema_object_properties(model: Type[Model], apistrap: Optional[Apistrap]) -> Dict[str, Any]:
    """
    Convert all fields of a model to OpenAPI 3 SchemaObject Properties objects

    :param model: the model to be converted
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a dictionary with field names as keys and SchemaObjects as values
    """
    properties = {}

    for field in model._fields.values():
        serialized_name = _get_serialized_name(field)
        schema_object = _field_to_schema_object(field, apistrap)

        if schema_object is not None:
            properties[serialized_name] = schema_object

    return properties


def _union_field_to_schema_object(field: UnionType, apistrap: Optional[Apistrap], name: str = None) -> Dict[str, Any]:
    """
    Convert a union field to an OpenAPI 3 SchemaObject.

    :param field: the field to be converted
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a schema
    """

    if apistrap is None:
        raise ValueError("Union fields cannot work without an apistrap instance")

    types = field._types.values()
    schemas = []

    for t in types:
        schema = _field_to_schema_object(t, apistrap)
        if schema not in schemas:  # sets cannot be used here because dicts are not hashable
            schemas.append(schema)

    if len(schemas) == 1:
        return schemas.pop()

    return {
        "$ref": apistrap.add_schema_definition(
            snake_to_camel(f"{name or _get_serialized_name(field)}_union", uppercase_first=True), {"anyOf": schemas}
        )
    }


def _poly_model_field_to_schema_object(field: PolyModelType, apistrap: Optional[Apistrap]) -> Dict[str, Any]:
    """
    Convert a poly model field to an OpenAPI 3 SchemaObject.

    :param field: the field to be converted
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a schema
    """
    return {"anyOf": [schematics_model_to_schema_object(model, apistrap) for model in field.model_classes]}


def _discriminated_model_field_to_schema_object(
    field: DiscriminatedModelType, apistrap: Optional[Apistrap]
) -> Dict[str, Any]:
    """
    Convert a discriminated model field to an OpenAPI 3 SchemaObject.

    :param field: the field to be converted
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a schema
    """
    if apistrap is None:
        raise ValueError("Discriminated model fields cannot work without an apistrap instance")

    result = _poly_model_field_to_schema_object(field, apistrap)
    result["discriminator"] = {
        "propertyName": field.discriminator_field_name,
        "mapping": {
            key: schematics_model_to_schema_object(model, apistrap)["$ref"] for key, model in field.type_map.items()
        },
    }

    return {"$ref": apistrap.add_schema_definition(field.model_name, result)}


def _field_to_schema_object(field: BaseType, apistrap: Optional[Apistrap]) -> Optional[Dict[str, Any]]:
    """
    Convert a field definition to OpenAPI 3 schema.

    :param field: the field to be converted
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a schema
    """

    if isinstance(field, ModelType):
        return _model_field_to_schema_object(field, apistrap)
    elif isinstance(field, ListType):
        if isinstance(field.field, ModelType):
            return _model_array_to_schema_object(field, apistrap)
        elif isinstance(field.field, BaseType):
            return _primitive_array_to_schema_object(field)
    elif isinstance(field, DictType):
        if isinstance(field.field, ModelType):
            return _model_dict_to_schema_object(field, apistrap)
        elif isinstance(field.field, UnionType):
            return _union_dict_to_schema_object(field, apistrap)
        elif isinstance(field.field, BaseType):
            return _primitive_dict_to_schema_object(field)
    elif isinstance(field, StringType):
        return _string_field_to_schema_object(field, apistrap)
    elif isinstance(field, AnyType):
        return {}
    elif isinstance(field, UnionType):
        return _union_field_to_schema_object(field, apistrap)
    elif isinstance(field, DiscriminatedModelType):
        return _discriminated_model_field_to_schema_object(field, apistrap)
    elif isinstance(field, PolyModelType):
        return _poly_model_field_to_schema_object(field, apistrap)
    elif isinstance(field, BaseType):
        return _primitive_field_to_schema_object(field)

    return None


SCHEMATICS_TYPE_TO_JSON_TYPE = {
    NumberType: "number",
    IntType: "integer",
    LongType: "integer",
    FloatType: "number",
    DecimalType: "number",
    BooleanType: "boolean",
}

SCHEMATICS_OPTIONS_TO_JSON_SCHEMA = {
    "max_length": "maxLength",
    "min_length": "minLength",
    "regex": "pattern",
    "min_value": "minimum",
    "max_value": "maximum",
    "min_size": "minItems",
    "max_size": "maxItems",
}


def _get_field_type(field: BaseType):
    for cls in getmro(field.__class__):
        if cls in SCHEMATICS_TYPE_TO_JSON_TYPE.keys():
            return SCHEMATICS_TYPE_TO_JSON_TYPE[cls]

    return "string"


def _extract_model_description(field: BaseType) -> Dict[str, Any]:
    """
    Load title and description from Schematics metadata.

    :param field: field to extract metadata from
    :return a dict with optional title and description keys
    """

    metadata = field.metadata
    data = {}

    if "label" in metadata:
        data["title"] = metadata["label"]

    if "description" in metadata:
        data["description"] = metadata["description"]

    return data


def _primitive_field_to_schema_object(field: BaseType) -> Dict[str, str]:
    schema = {"type": _get_field_type(field)}

    schema.update(_extract_model_description(field))

    for schematics_attr, json_schema_attr in SCHEMATICS_OPTIONS_TO_JSON_SCHEMA.items():
        if hasattr(field, schematics_attr):
            option_value = getattr(field, schematics_attr)
            if option_value is not None:
                schema[json_schema_attr] = option_value

    return schema


def _string_field_to_schema_object(field: StringType, apistrap: Optional[Apistrap] = None) -> Dict[str, str]:
    schema = _primitive_field_to_schema_object(field)

    if field.choices is not None:
        if apistrap is None:
            schema["enum"] = field.choices
        else:
            name = snake_to_camel(field.name)
            name = name[0].upper() + name[1:]

            schema = {"$ref": apistrap.add_schema_definition(name, {"type": "string", "enum": field.choices})}

    return schema


def _get_required_fields(model: Type[Model]) -> Generator[str, None, None]:
    """
    Extract required field names from a Schematics model

    :param model:
    :return: a generator of field names
    """

    for field in model._fields.values():
        if getattr(field, "required", False):
            yield _get_serialized_name(field)


def _model_array_to_schema_object(field: ModelType, apistrap: Optional[Apistrap]) -> Dict[str, Any]:
    """
    Get a SchemaObject for a list of given models

    :param field: the field field to be converted
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a SchemaObject
    """

    model = field.field.model_class

    schema = {
        "type": "array",
        "title": f"List of {model.__name__}",
        "items": schematics_model_to_schema_object(model, apistrap),
    }

    schema.update(_extract_model_description(field))

    return schema


def _model_dict_to_schema_object(field: DictType, apistrap: Optional[Apistrap]) -> Dict[str, Any]:
    """
    Get a SchemaObject for a dictionary of given models

    :param field: the field to be converted
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a SchemaObject
    """

    model = field.field.model_class

    schema = {
        "type": "object",
        "title": f"Dictionary of {model.__name__}",
        "additionalProperties": schematics_model_to_schema_object(model, apistrap),
    }

    schema.update(_extract_model_description(field))

    return schema


def _union_dict_to_schema_object(field: DictType, apistrap: Optional[Apistrap]) -> Dict[str, Any]:
    """
    Get a SchemaObject for a dictionary of given unions

    :param field: the field to be converted
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a SchemaObject
    """

    schema = {
        "type": "object",
        "title": f"Dictionary of {'|'.join(field.field.typenames)}",
        "additionalProperties": _union_field_to_schema_object(field.field, apistrap, _get_serialized_name(field)),
    }

    return schema


def _primitive_array_to_schema_object(field: ListType) -> Dict[str, Any]:
    """
    Get a SchemaObject for a list of primitive types

    :param field: the field that determines the value type
    :return: a SchemaObject
    """

    schema = {
        "type": "array",
        "title": f"List of {field.field.__class__.__name__}",
        "items": _field_to_schema_object(field.field, None),
    }

    schema.update(_extract_model_description(field))

    return schema


def _primitive_dict_to_schema_object(field: DictType) -> Dict[str, Any]:
    """
    Get a SchemaObject for a dictionary of primitive types

    :param field: the field that determines the value type
    :return: a SchemaObject
    """

    schema = {
        "type": "object",
        "title": f"Dictionary of {field.field.__class__.__name__}",
        "additionalProperties": _field_to_schema_object(field.field, None),
    }

    schema.update(_extract_model_description(field))

    return schema


def _model_field_to_schema_object(field: ModelType, apistrap: Optional[Apistrap]) -> Dict[str, Any]:
    """
    Get a SchemaObject for a model field.

    :param field: the field that determines the value type
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a SchemaObject
    """

    schema = schematics_model_to_schema_object(field.model_class, apistrap)
    schema.update(_extract_model_description(field))

    return schema


def schematics_model_to_schema_object(model: Type[Model], apistrap: Optional[Apistrap] = None) -> Dict[str, Any]:
    """
    Convert a Schematics model to an OpenAPI 3 SchemaObject

    :param model: the model to be converted
    :param apistrap: the extension used for adding reusable schema definitions
    :return: a SchemaObject
    """

    schema = {
        "type": "object",
        "title": model.__name__,
        "properties": (_model_fields_to_schema_object_properties(model, apistrap)),
    }

    required = list(_get_required_fields(model))

    if required:
        schema["required"] = required

    if apistrap is None:
        return schema  # There is no way to reuse the schema definition

    name = apistrap.add_schema_definition(model.__name__, schema)

    return {"$ref": name}
