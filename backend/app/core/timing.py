"""Timing helpers."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator


@contextmanager
def timed() -> Generator[dict, None, None]:
    """Yield a dict that receives a 'duration_ms' value on exit."""
    result: dict = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["duration_ms"] = round((time.perf_counter() - start) * 1000.0, 2)
