#!/usr/bin/env python3
"""Pharmacy Management System — entry point."""

from __future__ import annotations

import sys

from app.core.app import Application


def main() -> int:
    """Launch the application and return the exit code."""
    app = Application()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
