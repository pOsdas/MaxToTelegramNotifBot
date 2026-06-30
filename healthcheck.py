import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def fail(message: str) -> None:
    print(message)
    sys.exit(1)


def parse_datetime(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, str) or not value:
        fail(
            f"heartbeat field {field_name} "
            "is empty"
        )

    try:
        parsed = datetime.fromisoformat(
            value
        )
    except ValueError as exc:
        fail(
            f"invalid {field_name}: {exc}"
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


path = Path(
    os.getenv(
        "HEARTBEAT_PATH",
        "/app/runtime/data/heartbeat.json",
    )
)

if not path.exists():
    fail("heartbeat file does not exist")

try:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )
except Exception as exc:
    fail(
        f"invalid heartbeat json: {exc}"
    )

now = datetime.now(timezone.utc)

heartbeat_at = parse_datetime(
    payload.get("heartbeat_at"),
    "heartbeat_at",
)

heartbeat_age = (
    now - heartbeat_at
).total_seconds()

if heartbeat_age > 120:
    fail(
        "heartbeat is stale: "
        f"{heartbeat_age:.1f}s"
    )

parser_status = str(
    payload.get("parser_status")
    or "unknown"
)

if parser_status in {
    "degraded",
    "broken",
}:
    fail(
        "parser is unhealthy: "
        f"{parser_status}; "
        f"{payload.get('last_error')}"
    )

last_success_raw = payload.get(
    "last_success_at"
)

if last_success_raw:
    last_success = parse_datetime(
        last_success_raw,
        "last_success_at",
    )

    max_interval = int(
        os.getenv(
            "MAX_CHECK_INTERVAL_SECONDS",
            "3600",
        )
    )

    grace = int(
        os.getenv(
            "PARSER_SUCCESS_STALE_GRACE_SECONDS",
            "900",
        )
    )

    max_age = max_interval + grace

    success_age = (
        now - last_success
    ).total_seconds()

    if success_age > max_age:
        fail(
            "last successful MAX scan "
            "is stale: "
            f"{success_age:.1f}s "
            f"> {max_age}s"
        )

print(
    "ok: "
    f"status={payload.get('status', 'unknown')}, "
    f"parser={parser_status}, "
    f"heartbeat_age={heartbeat_age:.1f}s"
)
