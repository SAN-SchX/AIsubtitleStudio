import os
import sys
import threading
import time

import pytest

from ai_subtitle_studio.domain.errors import OperationCancelled, StudioError
from ai_subtitle_studio.media.process import run_tool


def test_timeout_reaps_child():
    start = time.monotonic()
    with pytest.raises(StudioError, match="limit czasu"):
        run_tool([sys.executable, "-c", "import time; time.sleep(60)"], timeout_s=0.1)
    assert time.monotonic() - start < 3


@pytest.mark.parametrize("attempt", range(3))
def test_running_process_cancellation_reaps_child(tmp_path, attempt):
    pid_file = tmp_path / "pid"
    cancel = threading.Event()
    code = (
        "import os,sys,time; from pathlib import Path; "
        "Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)"
    )

    def trigger():
        deadline = time.monotonic() + 3
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        cancel.set()

    thread = threading.Thread(target=trigger)
    thread.start()
    try:
        with pytest.raises(OperationCancelled):
            run_tool([sys.executable, "-c", code, str(pid_file)], timeout_s=5, cancel=cancel)
    finally:
        thread.join(timeout=4)
    pid = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_missing_and_failed_program():
    with pytest.raises(StudioError, match="Brak programu"):
        run_tool(["/no/such/ffprobe"], timeout_s=1)
    with pytest.raises(StudioError, match="odrzucił"):
        run_tool([sys.executable, "-c", "raise SystemExit(2)"], timeout_s=2)
