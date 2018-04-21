from typing import List, Dict


class SwaggerExtensionError(Exception):
    """
    Raised on incorrect usage of the Swagger extension
    """


class ApiClientError(Exception):
    pass


class InvalidFieldsError(ApiClientError):
    def __init__(self, errors: Dict[str, List[str]]):
        super().__init__("Invalid input: {}".format(str(errors)))
        self.errors = errors


class ApiServerError(Exception):
    pass


class UnexpectedResponseError(ApiServerError):
    def __init__(self, response_class: type):
        super().__init__("Unexpected response class: {}".format(response_class.__name__))


class InvalidResponseError(ApiServerError):
    def __init__(self, errors: Dict[str, List[str]]):
        super().__init__("Invalid input: {}".format(str(errors)))
        self.errors = errors
