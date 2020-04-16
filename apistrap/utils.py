import inspect
import traceback
from typing import Any, Callable, Dict, Mapping, Type, Union

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


def snake_to_camel(value: str, *, uppercase_first: bool = False) -> str:
    """
    Convert a string from snake_case to camelCase
    """
    result = "".join(x.capitalize() or "_" for x in value.split("_"))

    if uppercase_first:
        return result

    return result[0].lower() + result[1:]


def get_function_perspective_globals(function: Callable) -> Dict[str, Any]:
    """
    Extract global variables from the stack of a function.

    :param function: the function whose stack should be examined.
    :return: a merged dictionary of globals
    """

    globs = {}
    stack = inspect.stack()

    for frame in stack:
        if frame.filename == inspect.getsourcefile(function):
            globs.update(frame.frame.f_globals)

    module = inspect.getmodule(function)
    if module:
        globs.update(inspect.getmembers(module))

    return globs


def resolve_fw_decl(function: Callable, annotation: Union[None, str, Type]) -> Type:
    """
    Resolve a parameter annotation.

    :param function: the function that owns the annotation
    :param annotation: an annotation string
    :return: the resolved annotation
    """
    if annotation is None:
        raise ValueError("NoneType parameter annotations are not supported")

    if not isinstance(annotation, str):
        return annotation

    globs = get_function_perspective_globals(function)

    return eval(annotation, globs)


def get_type_hints(function: Callable) -> Dict[str, Type]:
    """
    Get a dictionary of resolved type annotations for a function.
    """

    return {name: resolve_fw_decl(function, annotation) for name, annotation in function.__annotations__.items()}
