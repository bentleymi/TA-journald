"""Shared collection logic for TA-journald scripted inputs (journal disk usage + growth)."""
import json
import os
import re
import subprocess
import sys
import time

JOURNAL_DIR = "/var/log/journal"
ALARM_KB = 8388608

_UNITS = {"B": 1, "K": 1000, "M": 1000000, "G": 1000000000, "T": 1000000000000}
_SIZE_RE = re.compile(r"^(\d+(?:\.\d+)?)([BKMGT]?)$")


def _run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_size_kb(token):
    m = _SIZE_RE.match(token)
    if not m:
        return None
    val = _num(m.group(1))
    if val is None:
        return None
    return int(round(val * _UNITS.get(m.group(2), 1) / 1024.0))


def journalctl_disk_kb():
    out = _run(["journalctl", "--disk-usage"])
    if not out:
        return None
    for tok in out.split():
        kb = parse_size_kb(tok)
        if kb is not None:
            return kb
    return None


def walk_journal():
    total = 0
    count = 0
    oldest = None
    if not os.path.isdir(JOURNAL_DIR):
        return 0, 0, None
    for root, _dirs, files in os.walk(JOURNAL_DIR):
        for name in files:
            if not name.endswith(".journal"):
                continue
            try:
                st = os.stat(os.path.join(root, name))
            except OSError:
                continue
            total += st.st_size
            count += 1
            if oldest is None or st.st_mtime < oldest:
                oldest = st.st_mtime
    return int(round(float(total) / 1024.0)), count, oldest


def service_active():
    out = _run(["systemctl", "is-active", "systemd-journald"])
    return 1 if out is not None and out.strip() == "active" else 0


def discover():
    jkb = journalctl_disk_kb()
    kb, count, oldest = walk_journal()
    disk_kb = jkb if jkb is not None else kb
    if jkb is None and count == 0:
        status = "absent"
    elif disk_kb > ALARM_KB:
        status = "alarm"
    else:
        status = "ok"
    data = {
        "status": status,
        "disk_kb": disk_kb,
        "file_count": count,
        "service_active": service_active(),
    }
    if oldest is not None:
        data["oldest_age_hours"] = round((time.time() - oldest) / 3600.0, 2)
    return data


def events_payload(data):
    disk_kb = data.get("disk_kb")
    disk_kb = int(disk_kb) if disk_kb is not None else 0
    p = {
        "status": data.get("status", "absent"),
        "disk_kb": disk_kb,
        "size_mb": int(disk_kb / 1024),
        "file_count": int(data.get("file_count") or 0),
        "service_active": int(data.get("service_active") or 0),
    }
    if data.get("oldest_age_hours") is not None:
        p["oldest_age_hours"] = data["oldest_age_hours"]
    return p


def metrics_payload(data):
    disk_kb = data.get("disk_kb")
    disk_kb = int(disk_kb) if disk_kb is not None else 0
    p = {
        "disk_kb": disk_kb,
        "size_mb": int(disk_kb / 1024),
        "file_count": int(data.get("file_count") or 0),
        "service_active": int(data.get("service_active") or 0),
    }
    if data.get("oldest_age_hours") is not None:
        p["oldest_age_hours"] = data["oldest_age_hours"]
    return p


def emit(payload):
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()


def fail(message):
    sys.stderr.write("TA-journald collection error: %s\n" % message)
    return 1
