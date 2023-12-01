import time

def timeis(func):
    '''Decorator that reports the execution time.'''

    def wrap(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()

        print(func.__name__, end - start)
        return result

    return wrap


@timeis
def countdown(n):
    '''Counts down'''
    while n > 0:
        n -= 1


countdown(8)
countdown(1000)
 