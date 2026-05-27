"""
Validation service.

Runs configurable rules from the device profile against decoded data.
Rules are evaluated per-field and support:
  min / max          — numeric range check
  not_null           — field must be present and non-None
  rate_of_change_max — max allowed delta from the previous reading (stored in Redis)
"""

from typing import Any

import structlog

from services.decoder import get_profile

log = structlog.get_logger()

# Optional Redis client injected at startup for rate-of-change checks
_redis = None


def set_redis(client) -> None:
    global _redis
    _redis = client


def validate(
    dev_eui: str,
    decoded_data: dict[str, Any],
    profile_id: str,
) -> tuple[bool, list[str]]:
    """Return (is_valid, list_of_error_strings)."""
    profile = get_profile(profile_id)
    rules = profile.get("validation", {}).get("rules", [])
    errors: list[str] = []

    for rule in rules:
        field: str = rule["field"]
        value = decoded_data.get(field)

        if rule.get("not_null") and value is None:
            errors.append(f"{field}: required but missing")
            continue

        if value is None:
            continue

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue

        if "min" in rule and numeric < rule["min"]:
            errors.append(f"{field}: {numeric} below min {rule['min']}")

        if "max" in rule and numeric > rule["max"]:
            errors.append(f"{field}: {numeric} above max {rule['max']}")

        if "rate_of_change_max" in rule and _redis is not None:
            _check_rate_of_change(dev_eui, field, numeric, rule["rate_of_change_max"], errors)

    is_valid = len(errors) == 0
    if not is_valid:
        log.info("validator.failed", dev_eui=dev_eui, errors=errors)

    return is_valid, errors


def _check_rate_of_change(
    dev_eui: str,
    field: str,
    value: float,
    max_delta: float,
    errors: list[str],
) -> None:
    key = f"last_val:{dev_eui}:{field}"
    try:
        import asyncio

        prev_bytes = asyncio.get_event_loop().run_until_complete(_redis.get(key))
        if prev_bytes is not None:
            prev = float(prev_bytes)
            delta = abs(value - prev)
            if delta > max_delta:
                errors.append(
                    f"{field}: rate-of-change {delta:.4f} exceeds max {max_delta}"
                )
        asyncio.get_event_loop().run_until_complete(
            _redis.setex(key, 3600, str(value))
        )
    except Exception as exc:
        log.warning("validator.roc_check_failed", field=field, error=str(exc))
