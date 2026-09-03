#!/usr/bin/env python3
"""Thin shim — logic lives in the canonical taskman package."""
from taskman.mow.hydrate_specs import *  # noqa: F403
from taskman.mow.hydrate_specs import main

if __name__ == "__main__":
    raise SystemExit(main())
