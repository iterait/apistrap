from schematics import Model
from schematics.types import StringType


class ErrorResponse(Model):
    """
    An error message wrapper
    """
    
    message = StringType(required=True)