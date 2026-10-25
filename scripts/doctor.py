"""Run after installing the package: python scripts/doctor.py [--json]."""

import sys

from ai_subtitle_studio.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["doctor", *sys.argv[1:]]))
