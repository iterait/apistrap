from typing import List, Dict


class ApiClientError(BaseException):
    pass


class InvalidFieldsError(ApiClientError):
    def __init__(self, errors: Dict[str, List[str]]):
        super().__init__("Invalid input: {}".format(str(errors)))
        self.errors = errors
