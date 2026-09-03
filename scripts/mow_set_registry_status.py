#!/usr/bin/env python3
"""Thin shim — logic lives in the canonical taskman package."""
from taskman.mow.set_registry_status import *  # noqa: F403
from taskman.mow.set_registry_status import main

if __name__ == "__main__":
    raise SystemExit(main())
