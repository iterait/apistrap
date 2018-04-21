from schematics import Model
from schematics.types import StringType


class ErrorResponse(Model):
    message = StringType(required=True)