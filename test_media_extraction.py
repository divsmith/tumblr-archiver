#!/usr/bin/env python3
"""Wrapper: tests moved to the `tests/` directory.
Run `pytest` or execute this file to run the moved script.
"""
import runpy
import sys

if __name__ == "__main__":
    sys.exit(runpy.run_path("tests/test_media_extraction.py", run_name="__main__"))
