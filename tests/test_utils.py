from apistrap.utils import format_exception


class MyException(RuntimeError):
    pass


def foo():
    raise MyException("Testing exception message")


def goo():
    foo()


def test_format_exception():
    try:
        goo()
    except Exception as exception:
        exception_info = format_exception(exception)

        expected_keys = {"exception_type", "exception_message", "traceback"}
        assert set(exception_info.keys()) == expected_keys

        assert exception_info["exception_type"] == "MyException"
        assert exception_info["exception_message"] == "Testing exception message"

        assert len(exception_info["traceback"]) == 6
        assert exception_info["traceback"][-1].strip() == 'raise MyException("Testing exception message")'
