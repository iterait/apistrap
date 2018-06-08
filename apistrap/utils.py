import traceback
from typing import Mapping, Any

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
        'exception_type': type(exception).__name__,
        'exception_message': str(exception),
        'traceback': list(flatten([str(s).rstrip('\n').split('\n') for s in traceback_summary.format()]))
    }
