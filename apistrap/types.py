from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import List, Sequence, Iterable, Union

from schematics.exceptions import BaseError, CompoundError, ConversionError
from schematics.types import CompoundType, StringType, BooleanType


@dataclass
class FileResponse:
    filename_or_fp: Union[str, bytes, BytesIO]
    as_attachment: bool=False
    attachment_filename: str=None
    add_etags: bool=True
    cache_timeout: int=None
    conditional: bool=False
    last_modified: Union[datetime, int]=None


class TupleType(CompoundType):
    """A field for storing a fixed length tuple of items. The values must conform to the types
    specified by the ``fields`` parameter.

    Use it like this::

        ...
        age_weight = TupleType([StringType, IntType], required=False)

    """

    primitive_type = list
    native_type = tuple

    def __init__(self, fields, **kwargs):
        self.fields = [self._init_field(field, kwargs) for field in fields]
        super().__init__(**kwargs)

    def _repr_info(self):
        return 'TupleType(' + ', '.join([field.__class__.__name__ for field in self.fields]) + ')'

    def _mock(self, context=None):
        return tuple([field._mock(context) for field in self.fields])

    def _coerce(self, value):
        if not isinstance(value, (list, List, Sequence, Iterable)):
            raise ConversionError('Could not interpret the value as a list')

        if len(value) != len(self.fields):
            raise ConversionError('Value length ({}) does not match expected length ({}).'.format(len(value),
                                                                                                  len(self.fields)))
        return value

    def _convert(self, value, context, safe=False):
        self._coerce(value)

        data = []
        errors = {}
        for i, (val, field) in enumerate(zip(value, self.fields)):
            try:
                data.append(context.field_converter(field, val, context))
            except BaseError as exc:
                errors[i] = exc

        if errors:
            raise CompoundError(errors)
        return tuple(data)

    def _export(self, tup_instance, format, context):
        """The field export_level is ignored so it won't change tuple size / sequence of its elements."""
        data = []
        for value, field in zip(tup_instance, self.fields):
            shaped = field.export(value, format, context)
            data.append(shaped)
        return data
