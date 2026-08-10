import queue
import sys
import time

from tiddl_gui.runner import DownloadRunner


def _drain(q, timeout=5.0):
    messages = []
    deadline = time.monotonic() + timeout
    saw_done = False
    while time.monotonic() < deadline and not saw_done:
        try:
            msg = q.get(timeout=0.1)
        except queue.Empty:
            continue
        messages.append(msg)
        if msg[0] == "done":
            saw_done = True
    return messages


def test_runner_streams_output_lines_and_reports_done():
    q = queue.Queue()
    runner = DownloadRunner(q)
    command = [sys.executable, "-c", "print('hello'); print('world')"]

    runner.start(command)
    messages = _drain(q)

    lines = [m[1] for m in messages if m[0] == "line"]
    assert lines == ["hello", "world"]
    assert messages[-1] == ("done", 0)
    assert runner.is_running() is False


def test_runner_rejects_concurrent_start():
    q = queue.Queue()
    runner = DownloadRunner(q)
    command = [sys.executable, "-c", "import time; time.sleep(2)"]

    runner.start(command)
    try:
        raised = False
        try:
            runner.start(command)
        except RuntimeError:
            raised = True
        assert raised
    finally:
        runner.cancel()
        _drain(q)


def test_runner_cancel_stops_process_early():
    q = queue.Queue()
    runner = DownloadRunner(q)
    command = [
        sys.executable, "-c",
        "import time; print('start'); time.sleep(10); print('end')",
    ]

    runner.start(command)
    time.sleep(0.3)
    runner.cancel()
    messages = _drain(q, timeout=5.0)

    lines = [m[1] for m in messages if m[0] == "line"]
    assert lines == ["start"]
    done = [m for m in messages if m[0] == "done"]
    assert len(done) == 1
    assert done[0][1] != 0


def test_runner_reports_done_even_when_process_fails_to_start():
    q = queue.Queue()
    runner = DownloadRunner(q)
    command = ["this-executable-does-not-exist-anywhere.exe"]

    runner.start(command)
    messages = _drain(q)

    done = [m for m in messages if m[0] == "done"]
    assert len(done) == 1
    assert done[0][1] != 0
    assert runner.is_running() is False
