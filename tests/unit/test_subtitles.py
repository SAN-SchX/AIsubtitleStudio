import codecs

import pysubs2
import pytest

from ai_subtitle_studio.config import Settings
from ai_subtitle_studio.domain.errors import OutputConflictError, SubtitleError
from ai_subtitle_studio.subtitles.io import export_subtitles, load_subtitles


@pytest.mark.parametrize("language", ["pl", "en", "ja"])
def test_srt_round_trip(fixtures_dir, tmp_path, language):
    document = load_subtitles(fixtures_dir / f"{language}_reference.srt")
    output = tmp_path / f"{language}.srt"
    export_subtitles(document, output)
    result = load_subtitles(output)
    assert result.cues == document.cues
    assert output.read_text(encoding="utf-8").startswith("1\n")


def test_ass_preserves_styles_tags_comments_actors(fixtures_dir, tmp_path):
    source = fixtures_dir / "styles.ass"
    document = load_subtitles(source)
    assert "ASS_EFFECTS_UNVERIFIED" in document.warnings
    assert len(document.cues) == 1
    output = tmp_path / "copy.ass"
    export_subtitles(document, output)
    before, after = [pysubs2.load(str(path)) for path in (source, output)]
    assert before.equals(after)
    assert after.styles["Polski"].bold
    assert after[0].name == "Narrator"
    assert after[1].is_comment
    assert r"\k20" in after[0].text
    assert load_subtitles(output).cues == document.cues
    with pytest.raises(SubtitleError, match="formacie źródłowym"):
        export_subtitles(document, tmp_path / "flatten.srt")


def test_no_overwrite_source_destination_aliases(fixtures_dir, tmp_path):
    source = tmp_path / "original.srt"
    source.write_bytes((fixtures_dir / "pl_reference.srt").read_bytes())
    document = load_subtitles(source)
    before = source.read_bytes()
    for path in (source, tmp_path / "link.srt", tmp_path / "hardlink.srt"):
        if path.name == "link.srt":
            path.symlink_to(source)
        elif path.name == "hardlink.srt":
            import os

            os.link(source, path)
        with pytest.raises(OutputConflictError):
            export_subtitles(document, path)
    assert source.read_bytes() == before
    assert not list(tmp_path.glob(".aisub-*"))


@pytest.mark.parametrize("encoding,bom", [("utf-8", codecs.BOM_UTF8), ("utf-16", b"")])
def test_bom_and_unusual_indexes(tmp_path, encoding, bom):
    path = tmp_path / "bom.srt"
    path.write_bytes(
        bom + "97\r\n00:00:01,000 --> 00:00:02,000\r\nŻółć 日本語\r\n".encode(encoding)
    )
    document = load_subtitles(path)
    assert document.cues[0].text == "Żółć 日本語"
    assert document.cues[0].id == "cue-000001"


def test_legacy_encoding_requires_explicit_choice(tmp_path):
    source = tmp_path / "legacy.srt"
    source.write_bytes("1\n00:00:01,000 --> 00:00:02,000\nZażółć\n".encode("cp1250"))
    with pytest.raises(SubtitleError, match="kodowanie"):
        load_subtitles(source)
    assert load_subtitles(source, encoding="cp1250").cues[0].text == "Zażółć"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "nonsense",
        "1\n00:00:02,000 --> 00:00:01,000\nx",
        "1\n00:00:01,000 --> 00:00:01,000\nx",
        "1\n-01:00:00,000 --> 00:00:01,000\nx",
        "1\n00:60:00,000 --> 00:00:01,000\nx",
        "1\n00:00:00,000 --> 00:00:01,000\n\x00x",
        "1\n00:00:00,000 --> 00:00:01,000\n   ",
    ],
)
def test_malformed_input_is_not_silently_repaired(tmp_path, text):
    path = tmp_path / "bad.srt"
    path.write_text(text)
    with pytest.raises(SubtitleError):
        load_subtitles(path)


def test_size_limit(tmp_path):
    path = tmp_path / "large.srt"
    path.write_bytes(b"x" * 33)
    with pytest.raises(SubtitleError, match="limit"):
        load_subtitles(path, settings=Settings(subtitle_limit_bytes=32))


def test_srt_exact_text_including_html_braces_backslashes(tmp_path):
    text = r"<b>Żółć</b> <font color='red'>日本語</font> {literal} \N"
    source = tmp_path / "tags.srt"
    source.write_text(f"42\n00:00:01,000 --> 00:00:02,000\n{text}\nDruga linia\n")
    document = load_subtitles(source)
    output = tmp_path / "copy.srt"
    export_subtitles(document, output)
    assert load_subtitles(output).cues[0].text == text + "\nDruga linia"


def test_long_unicode_line_is_not_truncated(tmp_path):
    source = tmp_path / "long.srt"
    text = "日本語 Zażółć " * 1000
    source.write_text(f"1\n00:00:01,000 --> 00:00:02,000\n{text.rstrip()}\n")
    output = tmp_path / "copy.srt"
    document = load_subtitles(source)
    export_subtitles(document, output)
    assert load_subtitles(output).cues == document.cues


def test_ass_extension_sections_survive_copy(fixtures_dir, tmp_path):
    source = tmp_path / "extended.ass"
    text = (fixtures_dir / "styles.ass").read_text() + "\n[Private Extension]\nKey: preserve me\n"
    source.write_text(text)
    document = load_subtitles(source)
    output = tmp_path / "copy.ass"
    export_subtitles(document, output)
    assert output.read_text() == text


@pytest.mark.parametrize(
    "replacement",
    ["Format: Start, End, Text", "Dialogue: 0,0:90:00.00,0:00:06.50,x", "Dialogue: broken"],
)
def test_unsupported_ass_layout_or_invalid_event_fails(fixtures_dir, tmp_path, replacement):
    text = (fixtures_dir / "styles.ass").read_text()
    if replacement.startswith("Format:"):
        lines = text.splitlines()
        position = lines.index("[Events]") + 1
        lines[position] = replacement
        text = "\n".join(lines)
    else:
        text += "\n" + replacement + "\n"
    source = tmp_path / "bad.ass"
    source.write_text(text)
    with pytest.raises(SubtitleError):
        load_subtitles(source)
