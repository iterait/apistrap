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

        for arg in sig.parameters.values():
            if arg.name not in self.ignored_args:
                param_data = {
                    "in": "path",
                    "name": arg.name
                }

                if arg.annotation in self.type_map:
                    param_data["type"] = self.type_map[arg.annotation]

                wrapped_func.specs_dict["parameters"].append(param_data)

        return wrapped_func
