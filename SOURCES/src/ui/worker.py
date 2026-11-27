"""Background task runner: worker threads + ``queue.Queue`` + ``root.after`` polling.

Golden Tcl/Tk rule: the worker thread only touches NumPy / pandas / crypto objects. Every
callback (``on_success`` / ``on_error`` / ``on_busy_change``) is invoked from ``_poll`` which
runs on the Tk main thread, so callbacks may freely update widgets, ``ImageTk.PhotoImage``
objects and ``canvas.draw_idle()``.
"""

from __future__ import annotations

import queue
import sys
import threading
import traceback
import tkinter as tk
from collections.abc import Callable
from typing import Any

SuccessCallback = Callable[[Any], None]
ErrorCallback = Callable[[BaseException, str], None]


class TaskRunner:
    def __init__(
        self,
        root: tk.Misc,
        *,
        on_busy_change: Callable[[bool], None] | None = None,
        poll_ms: int = 40,
    ) -> None:
        self._root = root
        self._queue: queue.Queue[tuple[str, Callable | None, Any, str]] = queue.Queue()
        self._active = 0
        self._after_id: str | None = None
        self._on_busy_change = on_busy_change
        self._poll_ms = poll_ms
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._active > 0

    @property
    def active_tasks(self) -> int:
        return self._active

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_success: SuccessCallback | None = None,
        on_error: ErrorCallback | None = None,
        **kwargs: Any,
    ) -> threading.Thread:
        """Run ``fn(*args, **kwargs)`` on a daemon thread; callbacks run on the main thread."""
        if self._closed:
            raise RuntimeError("TaskRunner has been shut down")
        self._active += 1
        if self._active == 1:
            self._notify_busy(True)

        def target() -> None:
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001 - forwarded to the main thread
                self._queue.put(("error", on_error, exc, traceback.format_exc()))
            else:
                self._queue.put(("ok", on_success, result, ""))

        thread = threading.Thread(target=target, name=f"ct204-{getattr(fn, '__name__', 'task')}",
                                  daemon=True)
        thread.start()
        self._schedule_poll()
        return thread

    def shutdown(self) -> None:
        """Stop polling (call before destroying the root window)."""
        self._closed = True
        if self._after_id is not None:
            try:
                self._root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    # ------------------------------------------------------------------ main thread
    def _schedule_poll(self) -> None:
        if self._after_id is None and not self._closed:
            try:
                self._after_id = self._root.after(self._poll_ms, self._poll)
            except tk.TclError:
                self._after_id = None

    def _poll(self) -> None:
        self._after_id = None
        if self._closed:
            return
        while True:
            try:
                kind, callback, payload, tb = self._queue.get_nowait()
            except queue.Empty:
                break
            self._active -= 1
            if self._closed:
                continue
            try:
                if kind == "ok":
                    if callback is not None:
                        callback(payload)
                elif callback is not None:
                    callback(payload, tb)
                else:
                    sys.stderr.write(tb)
            except Exception:  # noqa: BLE001 - a broken callback must not kill the loop
                sys.stderr.write(traceback.format_exc())
        if self._closed:
            return
        if self._active > 0:
            self._schedule_poll()
        else:
            self._notify_busy(False)

    def _notify_busy(self, busy: bool) -> None:
        if self._on_busy_change is not None:
            try:
                self._on_busy_change(busy)
            except tk.TclError:
                pass
