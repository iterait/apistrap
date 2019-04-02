from datetime import datetime
from io import BytesIO
from typing import Union
from typing.io import BinaryIO

from schematics.exceptions import BaseError, CompoundError, ValidationError
from schematics.types import FloatType, ListType


class FileResponse:
    """
    File response used instead of `flask.send_file`.
    Note that MIME type should preferably be handled by `responds_with` decorator.
    """

    def __init__(
        self,
        filename_or_fp: Union[str, BinaryIO, BytesIO],
        as_attachment: bool = False,
        attachment_filename: str = None,
        add_etags: bool = True,
        cache_timeout: int = None,
        conditional: bool = False,
        last_modified: Union[datetime, int] = None,
        mimetype=None,
    ):
        self.filename_or_fp = filename_or_fp
        self.as_attachment = as_attachment
        self.attachment_filename = attachment_filename
        self.add_etags = add_etags
        self.cache_timeout = cache_timeout
        self.conditional = conditional
        self.last_modified = last_modified
        self.mimetype = mimetype


class TupleType(ListType):
    """A field for storing a fixed length tuple of items. The values must conform to the type
    specified by the ``field`` parameter.

    Use it like this::

        ...
        coords = TupleType(IntType, 3, required=False)

    """

    primitive_type = list
    native_type = tuple

    def __init__(self, field, length, **kwargs):
        self.field = self._init_field(field, kwargs)
        super().__init__(field, min_size=length, max_size=length, **kwargs)

    def _repr_info(self):
        return f"TupleType({self.field.__class__.__name__}, {self.max_size})"

    def _mock(self, context=None):
        return tuple([self.field._mock(context) for _ in range(self.max_size)])

    def _convert(self, value, context, safe=False):
        self._coerce(value)

        data = []
        errors = {}
        for i, val in enumerate(value):
            try:
                data.append(context.field_converter(self.field, val, context))
            except BaseError as exc:
                errors[i] = exc

        if errors:
            raise CompoundError(errors)
        return tuple(data)

    def _export(self, tup_instance, format, context):
        """The field export_level is ignored so it won't change tuple size / sequence of its elements."""
        data = []
        for value in tup_instance:
            shaped = self.field.export(value, format, context)
            data.append(shaped)
        return data


class NonNanFloatType(FloatType):
    """
    FloatType replacing NaN to zeros when transformed to JSON.
    Good for endpoint responses since JSON doesn't support NaNs but Python does.
    """

    _NOT_SET_VALUE = object()

    def __init__(self, default_value: Union[float, object] = _NOT_SET_VALUE, **kwargs):
        self._default_value = default_value
        super().__init__(**kwargs)

    def to_native(self, value, context=None):
        try:
            import numpy as np
        except ImportError as ex:
            raise ImportError('NonNanFloatType requires Numpy.') from ex

        if np.isreal(value) and np.isscalar(value) and np.isnan(value):  # detect NaN
            if self._default_value == NonNanFloatType._NOT_SET_VALUE:  # user hasn't set the default value
                raise ValidationError("The value is NaN")
            value = self._default_value
        return super().to_native(value, context)
