import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import pysubs2
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("variant", ["reference", "plus8", "minus3", "fps", "jump"])
def test_fixture_matches_literal_golden(variant):
    expected = json.loads((ROOT / "tests/golden/timings.json").read_text())[variant]
    subs = pysubs2.load(str(ROOT / f"tests/fixtures/pl_{variant}.srt"))
    assert [[s.start, s.end] for s in subs] == expected


def test_generator_reproduces_all_files(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "fixture_generator", ROOT / "scripts/generate_fixtures.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate(tmp_path)
    for path in tmp_path.iterdir():
        assert path.read_bytes() == (ROOT / "tests/fixtures" / path.name).read_bytes()
    # Both FPS directions, no inference of offsets claimed here.
    assert module.transformed([(100100, 200200)], scale=Fraction(960, 1001)) == [(96000, 192000)]
    with pytest.raises(ValueError):
        module.transformed([(0, 1)], offset_ms=-3)


def test_missing_and_repeated_dialogue_are_explicit():
    ref = pysubs2.load(str(ROOT / "tests/fixtures/pl_reference.srt"))
    missing = pysubs2.load(str(ROOT / "tests/fixtures/pl_missing.srt"))
    assert ref[1].text == ref[2].text
    assert len(missing) == len(ref) - 1
    assert missing[1].start == ref[2].start
