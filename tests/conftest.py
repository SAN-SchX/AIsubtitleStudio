import shutil
import socket
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """The suite must never need an external service or download a model."""

    def blocked(*args, **kwargs):
        raise AssertionError("Network is disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture(scope="session")
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def media_files(tmp_path_factory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Local FFmpeg/FFprobe not installed")
    root = tmp_path_factory.mktemp("Zażółć 日本語 media")
    multi = root / "film '$(touch SHOULD_NOT_EXIST)'.mkv"
    silent = root / "silent.mp4"
    delayed = root / "delayed.mkv"

    def ffmpeg(*args):
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", *args],
            check=True,
            timeout=20,
            capture_output=True,
        )

    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=64x64:r=25:d=1.5",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1.5:sample_rate=16000",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:duration=1.5:sample_rate=16000",
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-map",
        "2:a",
        "-c:v",
        "mpeg4",
        "-threads",
        "1",
        "-c:a",
        "pcm_s16le",
        "-metadata:s:a:0",
        "language=jpn",
        "-metadata:s:a:0",
        "title=日本語",
        "-metadata:s:a:1",
        "language=eng",
        "-metadata:s:a:1",
        "title=English",
        str(multi),
    )
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=64x64:r=25:d=0.4",
        "-an",
        "-c:v",
        "mpeg4",
        "-threads",
        "1",
        str(silent),
    )
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=64x64:r=25:d=1.5",
        "-itsoffset",
        "0.25",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1:sample_rate=16000",
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        "mpeg4",
        "-threads",
        "1",
        "-c:a",
        "pcm_s16le",
        "-output_ts_offset",
        "3",
        str(delayed),
    )
    corrupt = root / "corrupt.mkv"
    corrupt.write_bytes(b"not a video\x00")
    return {"multi": multi, "silent": silent, "delayed": delayed, "corrupt": corrupt}
