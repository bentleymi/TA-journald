#!/usr/bin/env python3
"""Emit flat numeric metrics (one JSON event per cycle) for analytics."""
import sys

from journald_common import discover, emit, metrics_payload


def main():
    try:
        emit(metrics_payload(discover()))
    except Exception as e:
        emit({"error": str(e)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
