from schematics import Model
from schematics.types import StringType, DictType, BaseType
from typing import Mapping, Any


class ErrorResponse(Model):
    """
    An error message wrapper
    """

    message: str = StringType(required=True)
    debug_data: Mapping[str, Any] = DictType(BaseType, required=False, serialize_when_none=False)


class EmptyResponse(Model):
    """
    An empty message wrapper
    """
    pass
