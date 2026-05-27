"""
Payload decoder service.

Supports two decoding strategies:
  binary  — unpack raw bytes using a field map in the device profile
  json    — parse raw bytes as UTF-8 JSON
  passthrough — return data as-is (used by the generic profile)

Device profiles are loaded from JSON files in the `device_profiles/` directory.
A profile looks like:

{
  "profile_id": "soil_sensor_v1",
  "decoder": {
    "type": "binary",
    "endian": ">",      // ">" big-endian (default), "<" little-endian
    "fields": [
      {"name": "temperature", "offset": 0, "length": 2, "dtype": "int16",  "scale": 0.01, "unit": "°C"},
      {"name": "moisture",    "offset": 2, "length": 2, "dtype": "uint16", "scale": 0.01, "unit": "%"}
    ]
  },
  "validation": { "rules": [...] }
}
"""

import base64
import json
import struct
from pathlib import Path
from typing import Any

import structlog

from config import settings

log = structlog.get_logger()

_DTYPE_FMT: dict[str, str] = {
    "uint8":   "B",
    "int8":    "b",
    "uint16":  "H",
    "int16":   "h",
    "uint32":  "I",
    "int32":   "i",
    "uint64":  "Q",
    "int64":   "q",
    "float32": "f",
    "float64": "d",
}

_profiles: dict[str, dict] = {}


def load_profiles() -> None:
    profiles_dir = Path(settings.device_profiles_dir)
    for path in profiles_dir.glob("*.json"):
        try:
            with path.open() as f:
                profile = json.load(f)
            pid = profile.get("profile_id", path.stem)
            _profiles[pid] = profile
            log.info("decoder.profile_loaded", profile_id=pid, path=str(path))
        except Exception as exc:
            log.error("decoder.profile_load_failed", path=str(path), error=str(exc))


def get_profile(profile_id: str) -> dict:
    return _profiles.get(profile_id) or _profiles.get("generic", {})


def decode(raw_payload_b64: str | None, profile_id: str) -> dict[str, Any]:
    """Decode a base64 application payload using the specified device profile."""
    profile = get_profile(profile_id)
    decoder_cfg = profile.get("decoder", {"type": "passthrough"})
    dtype = decoder_cfg.get("type", "passthrough")

    if dtype == "passthrough" or raw_payload_b64 is None:
        return {}

    try:
        raw = base64.b64decode(raw_payload_b64)
    except Exception:
        log.warning("decoder.bad_base64", profile_id=profile_id)
        return {"_error": "invalid base64"}

    if dtype == "json":
        return _decode_json(raw, profile_id)
    if dtype == "binary":
        return _decode_binary(raw, decoder_cfg, profile_id)

    return {"_raw_hex": raw.hex()}


def decode_direct(data: dict[str, Any], profile_id: str) -> dict[str, Any]:
    """Accept already-decoded data (direct ingestion path) — pass through unchanged."""
    return data


# ── internal helpers ────────────────────────────────────────────────────────

def _decode_json(raw: bytes, profile_id: str) -> dict[str, Any]:
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        log.warning("decoder.json_failed", profile_id=profile_id, error=str(exc))
        return {"_error": "json parse failed", "_raw_hex": raw.hex()}


def _decode_binary(raw: bytes, cfg: dict, profile_id: str) -> dict[str, Any]:
    endian = cfg.get("endian", ">")
    fields = cfg.get("fields", [])
    result: dict[str, Any] = {}

    for field in fields:
        name: str = field["name"]
        offset: int = field["offset"]
        length: int = field["length"]
        dtype: str = field.get("dtype", "uint8")
        scale: float = field.get("scale", 1.0)

        fmt_char = _DTYPE_FMT.get(dtype)
        if fmt_char is None:
            log.warning("decoder.unknown_dtype", dtype=dtype, field=name)
            continue

        fmt = f"{endian}{fmt_char}"
        try:
            (value,) = struct.unpack_from(fmt, raw, offset)
            result[name] = round(value * scale, 6)
            if "unit" in field:
                result[f"{name}_unit"] = field["unit"]
        except struct.error as exc:
            log.warning(
                "decoder.unpack_failed",
                field=name, offset=offset, length=length, error=str(exc),
            )
            result[name] = None

    return result
