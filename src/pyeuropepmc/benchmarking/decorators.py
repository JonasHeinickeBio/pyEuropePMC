from collections.abc import Callable
from dataclasses import dataclass
import functools
import time
from typing import Any


@dataclass
class TimingResult:
    function: str
    execution_time: float
    args: tuple
    kwargs: dict
    result: Any


def measure_time(warmup: int = 0, repetitions: int = 1):
    """Decorator to measure function execution time with optional warmup and repetition.

    Args:
        warmup: Number of warmup runs (default: 0)
        repetitions: Number of repetitions to average (default: 1)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> TimingResult:
            result: Any = None

            for _i in range(warmup):
                func(*args, **kwargs)

            times = []
            for _i in range(repetitions):
                start = time.perf_counter()
                result = func(*args, **kwargs)
                end = time.perf_counter()
                times.append(end - start)

            avg_time = sum(times) / len(times)

            return TimingResult(
                function=func.__name__,
                execution_time=avg_time,
                args=args,
                kwargs=kwargs,
                result=result,
            )

        return wrapper

    return decorator


def profile_function(func: Callable) -> Callable:
    """Decorator for profiling function execution with detailed timing information."""
    import cProfile
    from io import StringIO
    import pstats

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()

        try:
            profiler.enable()
            result = func(*args, **kwargs)
            profiler.disable()

            s = StringIO()
            stats = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            stats.print_stats(20)

            return result, s.getvalue()
        except Exception as e:
            profiler.disable()
            raise e

    return wrapper
