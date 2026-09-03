#!/usr/bin/env python3
"""Thin shim — logic lives in the canonical taskman package."""
from taskman.mow.preflight import *  # noqa: F403
from taskman.mow.preflight import main

if __name__ == "__main__":
    raise SystemExit(main())
