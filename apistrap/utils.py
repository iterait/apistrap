import inspect
import sys
import traceback
from typing import Any, Mapping

from more_itertools import flatten


def format_exception(exception: Exception) -> Mapping[str, Any]:
    """
    Format an exception into a dict containing exception information such as class name, message and traceback.

    Example:

        {
            'exception_type': 'RuntimeError'
            'exception_message': 'Cannot connect to database.',
            'traceback': ['  File "spam.py", line 3, in <module>',
                          '   spam.eggs()\n',
                          ...]
        }
    """

    traceback_summary = traceback.StackSummary.extract(traceback.walk_tb(exception.__traceback__))

    return {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "traceback": list(flatten([str(s).rstrip("\n").split("\n") for s in traceback_summary.format()])),
    }


def snake_to_camel(value):
    """
    Convert a string from snake_case to camelCase
    """
    result = "".join(x.capitalize() or "_" for x in value.split("_"))
    return result[0].lower() + result[1:]


def get_function_perspective_globals(function, level=0, max_level=None):
    globs = {}
    if level != max_level:
        stack = inspect.stack()
        for frame in stack:
            if frame.filename == inspect.getsourcefile(function):
                globs.update(frame.frame.f_globals)
    return globs


def resolve_fw_decl(function, annotation, globs=None, level=0, search_stack_depth=2):
    if annotation is None:
        raise ValueError("NoneType parameter annotations are not supported")

    if not isinstance(annotation, str):
        return annotation

    if globs is None:
        globs = get_function_perspective_globals(function, level + 1, level + 1 + search_stack_depth)

    return eval(annotation, globs)


def get_type_hints(function):
    return {
        name: resolve_fw_decl(function, annotation)
        for name, annotation in function.__annotations__.items()
    }
