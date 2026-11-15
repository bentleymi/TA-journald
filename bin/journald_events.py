#!/usr/bin/env python3
"""Emit one JSON event per cycle with journald log-plane metadata."""
import sys

from journald_common import discover, emit, events_payload


def main():
    try:
        emit(events_payload(discover()))
    except Exception as e:
        emit({"status": "unknown", "error": str(e)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
