import abc
from abc import ABCMeta
from apispec import APISpec
from apispec.utils import OpenAPIVersion
from schematics import Model
from typing import Type, Optional, Dict, Callable, List

from apistrap.decorators import TagsDecorator, IgnoreParamsDecorator, SecurityDecorator, IgnoreDecorator
from apistrap.errors import SwaggerExtensionError


class SecurityScheme(metaclass=ABCMeta):
    def __init__(self, name: str, enforcer: Callable):
        self.name = name
        self.enforcer = enforcer

    @abc.abstractmethod
    def to_dict(self):
        """
        Get the OpenAPI JSON description of the security scheme
        """


class OAuthFlowDefinition:
    def __init__(self, flow_type: str, scopes: Dict[str, str], auth_url: Optional[str] = None, token_url: Optional[str] = None):
        self.flow_type = flow_type
        self.scopes = scopes
        self.auth_url = auth_url
        self.token_url = token_url

    def to_dict(self):
        result = {
            "scopes": self.scopes
        }

        if self.auth_url is not None:
            result["authorizationUrl"] = self.auth_url

        if self.token_url is not None:
            result["tokenUrl"] = self.token_url

        return result


class OAuthSecurity(SecurityScheme):
    def __init__(self, name: str, enforcer: Callable, *flows: OAuthFlowDefinition):
        super().__init__(name, enforcer)
        self.flows = flows

    def to_dict(self):
        return {
            "type": "oauth2",
            "flows": {
                flow.flow_type: flow.to_dict()
                for flow in self.flows
            }
        }


class Apistrap(metaclass=ABCMeta):
    def __init__(self):
        self.spec = APISpec(openapi_version=OpenAPIVersion("3.0.2"), title="API created with Apistrap", version="1.0.0")
        self.description = None
        self.oauth_client_id = None
        self.oauth_client_secret = None
        self.security_schemes: List[SecurityScheme] = []
        self._spec_url = "/swagger.json"
        self._ui_url = "/apidocs"
        self._use_default_error_handlers = True

    def to_dict(self):
        result = self.spec.to_dict()

        if self.description:
            result["info"]["description"] = self.description

        return result

    @abc.abstractmethod
    def _is_bound(self) -> bool:
        """
        Check whether the extension is bound to an app.
        """

    def _ensure_not_bound(self, message: str):
        if self._is_bound():
            raise SwaggerExtensionError(message)

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
    def use_default_error_handlers(self) -> bool:
        """
        A flag that indicates if the extension should register its error handlers when binding it with an app
        """
        return self._use_default_error_handlers

    @use_default_error_handlers.setter
    def use_default_error_handlers(self, value: bool):
        self._ensure_not_bound("You cannot change the error handler settings after binding the extension with an app")
        self._use_default_error_handlers = value

    def add_request_definition(self, name: str, schema: dict):
        """
        Add a new request definition to the specification. If a different schema is supplied for an existing definition,
        a ValueError is raised.
        :param name: the name of the definition (without the '#/definitions/' part)
        :param schema: a JsonObject OpenAPI structure
        :return: the full path to the definition in the specification file (can be used directly with $ref)
        """

        components = self.spec.components.to_dict()
        if name in components["schemas"]:
            if components["schemas"][name] != schema:
                raise ValueError("Conflicting definitions of `{}`".format(name))
        else:
            self.spec.components.schema(name, schema)

        return f"#/components/schemas/{name}"

    def add_response_definition(self, name: str, schema: dict):
        """
        Add a new response definition to the specification. If a different schema is supplied for an existing definition,
        a ValueError is raised.
        :param name: the name of the definition (without the '#/definitions/' part)
        :param schema: a JsonObject OpenAPI structure
        :return: the full path to the definition in the specification file (can be used directly with $ref)
        """

        components = self.spec.components.to_dict()
        if name in components["responses"]:
            if components["responses"][name] != schema:
                raise ValueError("Conflicting definitions of `{}`".format(name))
        else:
            self.spec.components.response(name, schema)

        return f"#/components/responses/{name}"

    def add_security_scheme(self, scheme: SecurityScheme):
        """
        Add a security scheme to be used by the API.
        :param scheme: a description of the security scheme
        """

        self.security_schemes.append(scheme)
        self.spec.components.security_scheme(scheme.name, scheme.to_dict())

    def tags(self, *tags: str):
        """
        A decorator that adds tags to the OpenAPI specification of the decorated view function.
        """
        return TagsDecorator(tags)

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
    def responds_with(self, response_class: Type[Model], *, code: int = 200, description: Optional[str] = None,
                      mimetype: Optional[str] = None):
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
