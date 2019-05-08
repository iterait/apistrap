import abc
from abc import ABCMeta
from typing import Callable, Dict, List, Optional, Type, Union

from apispec import APISpec
from apispec.utils import OpenAPIVersion
from docstring_parser import parse as parse_doc
from schematics import Model

from apistrap.decorators import (
    AcceptsFileDecorator,
    IgnoreDecorator,
    IgnoreParamsDecorator,
    SecurityDecorator,
    TagsDecorator,
)
from apistrap.errors import ApistrapExtensionError
from apistrap.tags import TagData


class SecurityScheme(metaclass=ABCMeta):
    """
    Description of an authentication method.
    """

    def __init__(self, name: str, enforcer: Callable[[List[str]], Callable]):
        """
        :param name: Name of the scheme (used as the name in the OpenAPI specification)
        :param enforcer: A decorator that takes a list of scopes and makes sure the user has them
        """
        self.name = name
        self.enforcer = enforcer

    @abc.abstractmethod
    def to_openapi_dict(self):
        """
        Get a JSON-serializable object with an OpenAPI description of the security scheme
        """


class OAuthFlowDefinition:
    """
    A holder for the description of an OpenAPI OAuth flow
    """

    def __init__(
        self, flow_type: str, scopes: Dict[str, str], auth_url: Optional[str] = None, token_url: Optional[str] = None
    ):
        """
        :param flow_type: e.g. password, implicit, ...
        :param scopes: a dict of scope name : human-readable description of available scopes
        :param auth_url: OAuth 2 authentication endpoint URL (if applicable)
        :param token_url: OAuth 2 token endpoint URL (if applicable)
        """
        self.flow_type = flow_type
        self.scopes = scopes
        self.auth_url = auth_url
        self.token_url = token_url

    def to_openapi_dict(self):
        """
        :return: A dictionary to be used in the OpenAPI specification
        """
        result = {"scopes": self.scopes}

        if self.auth_url is not None:
            result["authorizationUrl"] = self.auth_url

        if self.token_url is not None:
            result["tokenUrl"] = self.token_url

        return result


class OAuthSecurity(SecurityScheme):
    """
    A description of an OAuth security scheme with an arbitrary list of OAuth 2 flows
    """

    def __init__(self, name: str, enforcer: Callable, *flows: OAuthFlowDefinition):
        """
        :param flows: A list of OAuth 2 flows allowed by the security scheme
        """
        super().__init__(name, enforcer)
        self.flows = flows

    def to_openapi_dict(self):
        return {"type": "oauth2", "flows": {flow.flow_type: flow.to_openapi_dict() for flow in self.flows}}


class Apistrap(metaclass=ABCMeta):
    """
    An abstract ancestor for extensions that bind Apistrap to a web framework
    """

    PARAMETER_TYPE_MAP = {int: "integer", str: "string"}

    def __init__(self):
        self.spec = APISpec(openapi_version=OpenAPIVersion("3.0.2"), title="API created with Apistrap", version="1.0.0")
        self.description = None
        self.oauth_client_id = None
        self.oauth_client_secret = None
        self.security_schemes: List[SecurityScheme] = []
        self._spec_url = "/spec.json"
        self._ui_url = "/apidocs"
        self._redoc_url = None
        self._use_default_error_handlers = True

    def to_openapi_dict(self):
        """
        :return: a dict representation of the OpenAPI spec that can be directly serialized to JSON or YAML
        """

        result = self.spec.to_dict()

        if self.description:
            result["info"]["description"] = self.description

        return result

    ######################################
    # Extension points for child classes #
    ######################################

    @abc.abstractmethod
    def _is_bound(self) -> bool:
        """
        Check whether the extension is bound to an app.
        """

    ###################
    # Utility methods #
    ###################

    def _ensure_not_bound(self, message: str) -> None:
        """
        Throw an exception if the extension is already bound

        :param message: the message of the exception
        """
        if self._is_bound():
            raise ApistrapExtensionError(message)

    def _is_route_ignored(self, method: str, handler) -> bool:
        """
        Check if a view handler should be ignored.

        :param method: the HTTP method
        :param handler: the handler function
        """

        if method.lower() not in ["get", "post", "put", "delete", "patch"]:
            return True

        if getattr(handler, "apistrap_ignore", False):
            return True

        return False

    def _parameter_annotation_to_openapi_type(self, annotation):
        return self.PARAMETER_TYPE_MAP.get(annotation, "string")

    def _summary_from_docblock(self, docblock: Optional[str]) -> str:
        if docblock is None:
            return ""

        return parse_doc(docblock).short_description

    def _parameters_from_docblock(self, docblock: Optional[str]) -> Dict[str, str]:
        if docblock is None:
            return {}

        return {
            param.arg_name: param.description for param in parse_doc(docblock).params if param.description.strip() != ""
        }

    ############################
    # Configuration properties #
    ############################

    @property
    def title(self) -> str:
        """
        A title of the OpenAPI specification (the name of the API)
        """
        return self.spec.title

    @title.setter
    def title(self, title: str):
        self.spec.title = title

    @property
    def spec_url(self) -> Optional[str]:
        """
        The URL where the extension should serve the OpenAPI specification. If it is None, the specification is not
        served at all.
        """
        return self._spec_url

    @spec_url.setter
    def spec_url(self, value):
        self._ensure_not_bound("You cannot configure the spec_url after binding the extension with an app")
        self._spec_url = value

    @property
    def ui_url(self) -> Optional[str]:
        """
        The URL where the extension should serve the Swagger UI. If it is None (or if the specification is not served),
        the UI is not served at all.
        """
        return self._ui_url

    @ui_url.setter
    def ui_url(self, value: Optional[str]):
        self._ensure_not_bound("You cannot change the UI url after binding the extension with an app")
        self._ui_url = value.rstrip("/") if value is not None else None

    @property
    def redoc_url(self) -> Optional[str]:
        """
        The URL where the extension should serve the ReDoc documentation. If it is None (or if the specification is not
        served), the UI is not served at all.
        """
        return self._redoc_url

    @redoc_url.setter
    def redoc_url(self, value: Optional[str]):
        self._ensure_not_bound("You cannot change the ReDoc url after binding the extension with an app")
        self._redoc_url = value.rstrip("/") if value is not None else None

    @property
    def use_default_error_handlers(self) -> bool:
        """
        A flag that indicates if the extension should register its error handlers when binding it with an app
        """
        return self._use_default_error_handlers

    @use_default_error_handlers.setter
    def use_default_error_handlers(self, value: bool):
        self._ensure_not_bound("You cannot change the error handler settings after binding the extension with an app")
        self._use_default_error_handlers = value

    ###################################
    # Component definition management #
    ###################################

    def add_request_definition(self, name: str, schema: dict):
        """
        Add a new request definition to the specification. If a different schema is supplied for an existing definition,
        a ValueError is raised.

        :param name: the name of the definition (without the '#/components/.../' part)
        :param schema: a JsonObject OpenAPI structure
        :return: the full path to the definition in the specification file (can be used directly with $ref)
        """

        components = self.spec.components.to_dict()
        if "schemas" in components and name in components["schemas"]:
            if components["schemas"][name] != schema:
                raise ValueError(f"Conflicting definitions of `{name}`")
        else:
            self.spec.components.schema(name, schema)

        return f"#/components/schemas/{name}"

    def add_response_definition(self, name: str, schema: dict):
        """
        Add a new response definition to the specification. If a different schema is supplied for an existing definition,
        a ValueError is raised.

        :param name: the name of the definition (without the '#/components/.../' part)
        :param schema: a JsonObject OpenAPI structure
        :return: the full path to the definition in the specification file (can be used directly with $ref)
        """

        components = self.spec.components.to_dict()
        if "responses" in components and name in components["responses"]:
            if components["responses"][name] != schema:
                raise ValueError(f"Conflicting definitions of `{name}`")
        else:
            self.spec.components.response(name, schema)

        return f"#/components/responses/{name}"

    def add_schema_definition(self, name: str, schema: dict):
        """
        Add a new schema definition to the specification. If a different schema is supplied for an existing definition,
        a ValueError is raised.

        :param name: the name of the definition (without the '#/components/.../' part)
        :param schema: a JsonObject OpenAPI structure
        :return: the full path to the definition in the specification file (can be used directly with $ref)
        """

        components = self.spec.components.to_dict()
        if "schemas" in components and name in components["schemas"]:
            if components["schemas"][name] != schema:
                raise ValueError(f"Conflicting definitions of `{name}`")
        else:
            self.spec.components.schema(name, schema)

        return f"#/components/schemas/{name}"

    def add_security_scheme(self, scheme: SecurityScheme):
        """
        Add a security scheme to be used by the API.

        :param scheme: a description of the security scheme
        """

        self.security_schemes.append(scheme)
        self.spec.components.security_scheme(scheme.name, scheme.to_openapi_dict())

    def add_tag_data(self, tag: TagData) -> None:
        """
        Add information about a tag to the specification.
        :param tag: data about the tag
        """

        spec = self.spec.to_dict()
        if "tags" not in spec or tag.name not in map(lambda t: t["name"], spec["tags"]):
            self.spec.tag(tag.to_dict())

    #######################
    # Decorator factories #
    #######################

    def tags(self, *tags: Union[str, TagData]) -> TagsDecorator:
        """
        A decorator that adds tags to the OpenAPI specification of the decorated view function.
        """
        return TagsDecorator(self, tags)

    def ignore(self):
        """
        A decorator that marks an endpoint as ignored so that the extension won't include it in the specification.
        """
        return IgnoreDecorator()

    def ignore_params(self, *ignored_params: str):
        """
        A decorator that tells Apistrap to ignore given parameter names when generating documentation for an operation.
        """
        return IgnoreParamsDecorator(ignored_params)

    def security(self, *scopes: str):
        """
        A decorator that enforces user authentication and authorization.
        """
        return SecurityDecorator(self, scopes)

    @abc.abstractmethod
    def responds_with(
        self,
        response_class: Type[Model],
        *,
        code: int = 200,
        description: Optional[str] = None,
        mimetype: Optional[str] = None,
    ):
        """
        A decorator that fills in response schemas in the Swagger specification. It also converts Schematics models
        returned by view functions to JSON and validates them.
        """

    @abc.abstractmethod
    def accepts(self, request_class: Type[Model]):
        """
        A decorator that validates request bodies against a schema and passes it as an argument to the view function.
        The destination argument must be annotated with the request type.
        """

    def accepts_file(self, mime_type: str = None):
        """
        A decorator used to declare that an endpoint accepts a file as the request body.
        """
        return AcceptsFileDecorator(mime_type)
