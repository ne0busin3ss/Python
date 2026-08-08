"""Decorator example: report how long a function takes to run."""

import functools
import time


def timeis(func):
    """Decorator that reports the execution time."""

    @functools.wraps(func)
    def wrap(*args, **kwargs):
        # perf_counter is monotonic; time.time() can jump if the
        # system clock is adjusted mid-measurement.
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            print(f"{func.__name__} {elapsed:.6f}s")

    return wrap


@timeis
def countdown(n):
    """Count down to zero."""
    while n > 0:
        n -= 1


if __name__ == "__main__":
    countdown(8)
    countdown(1000)
