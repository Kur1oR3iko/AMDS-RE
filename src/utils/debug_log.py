"""In-memory runtime log capture for the built-in debug window."""

from __future__ import annotations

import os
import sys
import threading
from collections import deque
from datetime import datetime
from pathlib import Path


def _fallback_log_path() -> Path | None:
    try:
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        log_dir = Path(local_app_data) / "AMDS"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "runtime.log"
    except Exception:
        return None


class RuntimeLogBuffer:
    def __init__(self, max_lines: int = 2000):
        self._lines = deque(maxlen=max_lines)
        self._lock = threading.Lock()

    def add(self, source: str, text: str):
        text = text.rstrip()
        if not text:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._lines.append(f"[{timestamp}] {source}: {text}")
        _append_log_file(source, text)

    def text(self) -> str:
        with self._lock:
            return "\n".join(self._lines)


class TeeStream:
    def __init__(self, original, source: str, log_buffer: RuntimeLogBuffer):
        self.original = original
        self.source = source
        self.log_buffer = log_buffer
        self._pending = ""

    def write(self, data):
        text = str(data)
        if self.original is not None:
            try:
                self.original.write(text)
            except Exception:
                pass
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self.log_buffer.add(self.source, line)

    def flush(self):
        if self.original is not None:
            try:
                self.original.flush()
            except Exception:
                pass
        if self._pending:
            self.log_buffer.add(self.source, self._pending)
            self._pending = ""

    def isatty(self):
        return getattr(self.original, "isatty", lambda: False)()


runtime_log = RuntimeLogBuffer()
_installed = False
_runtime_log_file = _fallback_log_path()


def _append_log_file(source: str, text: str):
    if _runtime_log_file is None or not text:
        return
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _runtime_log_file.open("a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {source}: {text}\n")
    except Exception:
        pass


def install_debug_logging():
    global _installed
    if _installed:
        return
    _installed = True

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = TeeStream(original_stdout, "stdout", runtime_log)
    sys.stderr = TeeStream(original_stderr, "stderr", runtime_log)

    original_excepthook = sys.excepthook

    def log_excepthook(exc_type, exc_value, traceback_obj):
        message = f"{exc_type.__name__}: {exc_value}"
        runtime_log.add("exception", message)
        original_excepthook(exc_type, exc_value, traceback_obj)

    sys.excepthook = log_excepthook
