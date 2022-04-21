from typing import Any, Dict, Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """
    An error message wrapper
    """

    message: str
    debug_data: Optional[Dict[str, Any]] = None


class EmptyResponse(BaseModel):
    """
    An empty message wrapper
    """
