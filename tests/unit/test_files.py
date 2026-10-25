import pytest

from ai_subtitle_studio.domain.errors import OutputConflictError
from ai_subtitle_studio.files import atomic_output, sidecar_path


def test_concurrent_output_wins_and_no_overwrite(tmp_path):
    target = tmp_path / "copy.srt"
    with pytest.raises(OutputConflictError):
        with atomic_output(target) as temporary:
            temporary.write_bytes(b"new")
            target.write_bytes(b"another writer")
    assert target.read_bytes() == b"another writer"
    assert not list(tmp_path.glob(".aisub-*"))


def test_cleanup_on_failure(tmp_path):
    target = tmp_path / "copy.srt"
    with pytest.raises(RuntimeError):
        with atomic_output(target) as temporary:
            temporary.write_bytes(b"partial")
            raise RuntimeError("failed")
    assert not target.exists()
    assert not list(tmp_path.iterdir())


def test_dangling_symlink_not_followed(tmp_path):
    output = tmp_path / "dangling.srt"
    output.symlink_to(tmp_path / "missing")
    with pytest.raises(OutputConflictError):
        with atomic_output(output):
            pytest.fail("must not open temp output")
    assert not (tmp_path / "missing").exists()


def test_sidecar_sanitizes_language_without_changing_title(tmp_path):
    assert sidecar_path(tmp_path / "Zażółć 日本語.mkv", "pl").name == "Zażółć 日本語.pl.srt"
    for language in ("../x", "pl/abc", "", "$(touch x)"):
        with pytest.raises(ValueError):
            sidecar_path(tmp_path / "film.mkv", language)
