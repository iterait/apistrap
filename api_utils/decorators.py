from inspect import signature


class autodoc:
    """
    A decorator that generates Swagger metadata based on the signature of the decorated function and black magic.
    The metadata is collected by Flasgger and used to generate API specs/docs.
    """

    type_map = {
        int: "integer",
        str: "string"
    }

    def __init__(self, *, ignored_args=()):
        self.ignored_args = ignored_args

    def __call__(self, wrapped_func):
        sig = signature(wrapped_func)
        wrapped_func.specs_dict = {
            "parameters": [],
            "responses": {}
        }

        wrapped_func.specs_dict["parameters"] = [
            {
                "in": "path",
                "name": arg.name,
                "type": self.type_map.get(arg.annotation, None)
            }
            for arg in sig.parameters.values()
            if arg.name not in self.ignored_args
        ]

        return wrapped_func
