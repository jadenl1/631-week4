#!/usr/bin/env python3
"""Compatibility entry point: Python now owns the entire pipeline."""
from pipeline import main

if __name__ == '__main__':
    raise SystemExit(main())
