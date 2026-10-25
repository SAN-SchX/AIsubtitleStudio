"""Rebuild original synthetic subtitle fixtures; never used by the application."""

from fractions import Fraction
from pathlib import Path

import pysubs2

TEXTS = {
    "pl": ["Zażółć gęślą jaźń.", "Tak.", "Tak.", "To jest koniec."],
    "en": ["Welcome home.", "Yes.", "Yes.", "This is the end."],
    "ja": ["お帰りなさい。", "はい。", "はい。", "これで終わりです。"],
}
BASE = [(5000, 6500), (15000, 16000), (121000, 122500), (130000, 132000)]


def transformed(
    times: list[tuple[int, int]],
    *,
    offset_ms: int = 0,
    scale: Fraction = Fraction(1),
    jump_at_ms: int | None = None,
    jump_ms: int = 0,
) -> list[tuple[int, int]]:
    """Produce bad fixture timings, not an estimator or production retimer."""
    result = []
    for start, end in times:
        delta = offset_ms + (jump_ms if jump_at_ms is not None and start >= jump_at_ms else 0)
        a, b = round(start * scale) + delta, round(end * scale) + delta
        if not 0 <= a < b:
            raise ValueError("Invalid synthetic interval")
        result.append((a, b))
    return result


def generate(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for lang, texts in TEXTS.items():
        variants = {"reference": BASE}
        if lang == "pl":
            variants.update(
                {
                    "plus8": transformed(BASE, offset_ms=8000),
                    "minus3": transformed(BASE, offset_ms=-3000),
                    "fps": transformed(BASE, scale=Fraction(1001, 960)),
                    "jump": transformed(BASE, jump_at_ms=120000, jump_ms=10000),
                }
            )
        for name, times in variants.items():
            subs = pysubs2.SSAFile()
            for (start, end), text in zip(times, texts, strict=True):
                subs.append(pysubs2.SSAEvent(start=start, end=end, text=text))
            subs.save(str(root / f"{lang}_{name}.srt"), encoding="utf-8")
    missing = pysubs2.load(str(root / "pl_reference.srt"))
    del missing[1]
    missing.save(str(root / "pl_missing.srt"), encoding="utf-8")
    ass = pysubs2.SSAFile()
    ass.info["Title"] = "Original synthetic fixture"
    ass.styles["Polski"] = pysubs2.SSAStyle(fontname="Arial", fontsize=30, bold=True)
    ass.append(
        pysubs2.SSAEvent(
            start=5000,
            end=6500,
            style="Polski",
            text=r"{\k20}Zażółć {\i1}日本語{\i0}",
            name="Narrator",
        )
    )
    ass.append(pysubs2.SSAEvent(start=5000, end=6000, text="Komentarz", type="Comment"))
    ass.save(str(root / "styles.ass"), encoding="utf-8")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "tests" / "fixtures")
