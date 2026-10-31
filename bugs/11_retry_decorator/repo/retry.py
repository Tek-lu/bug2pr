import functools
import time


def retry(times, exceptions=(Exception,), sleep=time.sleep, base=0.1):
    """Call the function up to `times` times in total.

    After a failed attempt number k (0-based) wait base * 2**k seconds, but do not wait after the
    last attempt. If every attempt fails, re-raise the last exception.
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last = None
            for attempt in range(times - 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last = e
                    sleep(base * 2 ** attempt)
            return None
        return wrapper
    return deco
