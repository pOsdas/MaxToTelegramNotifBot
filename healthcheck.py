from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


path = Path(os.getenv("HEARTBEAT_PATH", "/app/runtime/data/heartbeat.json"))
if not path.exists():
    print("heartbeat file does not exist")
    sys.exit(1)

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
    heartbeat_at = datetime.fromisoformat(payload["heartbeat_at"])
except Exception as exc:
    print(f"invalid heartbeat: {exc}")
    sys.exit(1)

age = (datetime.now(timezone.utc) - heartbeat_at).total_seconds()
if age > 120:
    print(f"heartbeat is stale: {age:.1f}s")
    sys.exit(1)

print(f"ok: {payload.get('status', 'unknown')}, age={age:.1f}s")
