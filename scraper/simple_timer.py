import time

_start_time: float | None = None


def start() -> None:
    global _start_time
    _start_time = time.time()


def end() -> float | None:
    if _start_time is None:
        return None
    return time.time() - _start_time
