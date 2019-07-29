import traceback
from typing import Any, Callable, Generator, Mapping

from more_itertools import flatten


def get_wrapped_function(func: Callable):
    """
    Get the actual function from a decorated function. This could end up in a loop on horribly mangled functions.
    """

    wrapped = getattr(func, "__wrapped__", None)

    if wrapped is None:
        return func

    return get_wrapped_function(wrapped)


def unwrap_function(func: Callable) -> Generator[Callable, None, None]:
    """
    Gradually unwrap a decorated function. The first yielded item is always the arguments and the last one is always the
    first function that is not a wrapper.
    """

    cursor = func

    while True:
        yield cursor
        cursor = getattr(cursor, "__wrapped__", None)

        if cursor is None:
            break


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
