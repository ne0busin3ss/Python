"""Minimal example of a function decorator."""

import functools


def hello_decorator(func):
    """Print a message before and after calling `func`."""

    # `wrapper` is a closure: it can still see `func` after
    # `hello_decorator` has returned.
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("Hello, this is before function execution")
        try:
            return func(*args, **kwargs)
        finally:
            # `finally` so the message prints even if `func` raises.
            print("This is after function execution")

    return wrapper


def function_to_be_used(label="the function"):
    """Print a message from inside the decorated function."""
    print(f"This is inside {label} !!")
    return label


if __name__ == "__main__":
    # `@hello_decorator` above the def is sugar for exactly this line:
    function_to_be_used = hello_decorator(function_to_be_used)

    result = function_to_be_used("my function")
    print(f"returned: {result!r}, name preserved: {function_to_be_used.__name__}")
