import pytest

from ai_subtitle_studio.cli import main


def test_download_cli_requires_explicit_consent(capsys):
    assert main(["download-model"]) == 1
    assert "jawnej zgody" in capsys.readouterr().out


def test_transcribe_cli_requires_paths():
    with pytest.raises(SystemExit) as result:
        main(["transcribe"])
    assert result.value.code == 2


def test_negative_stream_rejected_by_cli():
    with pytest.raises(SystemExit) as result:
        main(["transcribe", "--audio-stream", "-1"])
    assert result.value.code == 2
