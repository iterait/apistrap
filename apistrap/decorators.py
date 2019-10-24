from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Sequence, Type, Union

from schematics import Model

from apistrap.tags import TagData

if TYPE_CHECKING:  # pragma: no cover
    from apistrap.extension import SecurityScheme


class IgnoreDecorator:
    """
    Marks an endpoint as ignored so that Apistrap doesn't include it in the specification.
    """


@dataclass(frozen=True)
class IgnoreParamsDecorator:
    """
    Marks specified function parameters as ignored for the purposes of generating a specification
    """

    ignored_params: Sequence[str]


@dataclass(frozen=True)
class RespondsWithDecorator:
    """
    Specifies the format of the response. The response is automatically validated by Apistrap.
    """

    response_class: Type[Model]
    code: int = 200
    description: Optional[str] = None
    mimetype: Optional[str] = None


@dataclass(frozen=True)
class AcceptsDecorator:
    """
    Specifies the format of the request body and injects it as an argument to the view handler.
    The destination parameter must be annotated with a corresponding type.
    """

    request_class: Type[Model]
    mimetypes: Sequence[str] = ("application/json",)


@dataclass(frozen=True)
class AcceptsFileDecorator:
    """
    Declares that an endpoint accepts a file upload as the request body.
    """

    mime_type: str


@dataclass(frozen=True)
class AcceptsQueryStringDecorator:
    """
    Declares that an endpoint accepts query string parameters.
    """

    parameter_names: Sequence[str]


@dataclass(frozen=True)
class TagsDecorator:
    """
    Adds tags to the OpenAPI specification of the decorated view function.
    """

    tags: Sequence[Union[str, TagData]]


@dataclass(frozen=True)
class SecurityDecorator:
    """
    Enforces user authentication and authorization.
    """

    scopes: Sequence[str]
    security_scheme: Optional[SecurityScheme] = None
