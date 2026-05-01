"""Shared background executor for IO-heavy helper work."""

from concurrent.futures import ThreadPoolExecutor
from os import cpu_count


_MAX_WORKERS = max(4, min(8, (cpu_count() or 4)))
_IO_EXECUTOR = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="amds-io")


def submit_io(func, *args, **kwargs):
    """Submit a small IO/network task to the shared executor."""
    return _IO_EXECUTOR.submit(func, *args, **kwargs)
