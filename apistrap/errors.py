from typing import Dict, List


class ApistrapExtensionError(Exception):
    """
    Raised on incorrect usage of the Apistrap extension
    """


class ApiClientError(Exception):
    """
    An exception raised when the user of the API makes an invalid request
    """


class InvalidFieldsError(ApiClientError):
    """
    An exception raised when the user of the API sends a malformed request object
    """

    def __init__(self, errors: Dict[str, List[str]]):
        super().__init__(f"Invalid input: `{str(errors)}`")
        self.errors = errors


class ApiServerError(Exception):
    """
    An exception raised when the server encounters an error
    """


class UnexpectedResponseError(ApiServerError):
    """
    An exception raised when a view function returns a response of an unexpected type
    """

    def __init__(self, response_class: type):
        super().__init__(f"Unexpected response class: `{response_class.__name__}`")


class InvalidResponseError(ApiServerError):
    """
    An exception raised when a view function returns a malformed response
    """

    def __init__(self, errors: Dict[str, List[str]]):
        super().__init__(f"Invalid input: `{str(errors)}`")
        self.errors = errors
