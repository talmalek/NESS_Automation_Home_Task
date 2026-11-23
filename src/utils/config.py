from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

import yaml


@dataclass(frozen=True)
class SamplingConfig:
    measurements_count: int
    total_duration_seconds: float
    sampling_frequency_hz: float

    @property
    def interval_seconds(self) -> float:
        return 1.0 / self.sampling_frequency_hz

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["interval_seconds"] = round(self.interval_seconds, 6)
        return data


@dataclass(frozen=True)
class AmmeterConfig:
    name: str
    port: int
    command: bytes
    method: str = ""
    host: str = "localhost"
    timeout_seconds: float = 2.0


def load_config(config_path: str) -> Dict[str, Any]:
    """Load and validate YAML configuration file."""
    with open(config_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid configuration in {config_path}: expected YAML mapping.")
    if not data.get("ammeters"):
        raise ValueError(f"Configuration in {config_path} must define at least one ammeter.")
    return data


def resolve_sampling_params(
    measurements_count: Optional[int] = None,
    total_duration_seconds: Optional[float] = None,
    sampling_frequency_hz: Optional[float] = None,
) -> SamplingConfig:
    """Resolve any 2-of-3 sampling parameters or validate all 3 for consistency.

    Mathematical relation: measurements_count == total_duration_seconds * sampling_frequency_hz
    """
    provided = sum(
        p is not None
        for p in (measurements_count, total_duration_seconds, sampling_frequency_hz)
    )
    if provided < 2:
        raise ValueError(
            "Provide at least 2 of: measurements_count, total_duration_seconds, sampling_frequency_hz."
        )

    if measurements_count is not None and (
        isinstance(measurements_count, bool)
        or not isinstance(measurements_count, int)
        or measurements_count <= 0
    ):
        raise ValueError("measurements_count must be a positive integer.")
    if total_duration_seconds is not None and (
        isinstance(total_duration_seconds, bool) or total_duration_seconds <= 0
    ):
        raise ValueError("total_duration_seconds must be > 0.")
    if sampling_frequency_hz is not None and (
        isinstance(sampling_frequency_hz, bool) or sampling_frequency_hz <= 0
    ):
        raise ValueError("sampling_frequency_hz must be > 0.")

    if sampling_frequency_hz is None:
        assert measurements_count is not None and total_duration_seconds is not None
        sampling_frequency_hz = measurements_count / total_duration_seconds
    elif measurements_count is None:
        assert total_duration_seconds is not None and sampling_frequency_hz is not None
        measurements_count = max(1, int(round(total_duration_seconds * sampling_frequency_hz)))
    elif total_duration_seconds is None:
        assert measurements_count is not None and sampling_frequency_hz is not None
        total_duration_seconds = measurements_count / sampling_frequency_hz
    else:
        expected_count = total_duration_seconds * sampling_frequency_hz
        if abs(measurements_count - expected_count) > 1.0:
            raise ValueError(
                f"Inconsistent sampling parameters: count={measurements_count}, "
                f"duration={total_duration_seconds}s, frequency={sampling_frequency_hz}Hz "
                f"(expected count ~ {expected_count:.2f})."
            )

    return SamplingConfig(
        measurements_count=int(measurements_count),
        total_duration_seconds=float(total_duration_seconds),
        sampling_frequency_hz=float(sampling_frequency_hz),
    )


def get_sampling_config(
    config: Dict[str, Any],
    measurements_count: Optional[int] = None,
    total_duration_seconds: Optional[float] = None,
    sampling_frequency_hz: Optional[float] = None,
) -> SamplingConfig:
    """Resolve sampling parameters using config defaults with optional runtime overrides."""
    defaults = config.get("testing", {}).get("sampling", {}) or {}
    override_provided = any(
        p is not None
        for p in (measurements_count, total_duration_seconds, sampling_frequency_hz)
    )
    if override_provided:
        provided_count = sum(
            p is not None
            for p in (measurements_count, total_duration_seconds, sampling_frequency_hz)
        )
        if provided_count >= 2:
            return resolve_sampling_params(
                measurements_count=measurements_count,
                total_duration_seconds=total_duration_seconds,
                sampling_frequency_hz=sampling_frequency_hz,
            )

    count = measurements_count if measurements_count is not None else defaults.get("measurements_count")
    duration = (
        total_duration_seconds
        if total_duration_seconds is not None
        else defaults.get("total_duration_seconds")
    )
    freq = (
        sampling_frequency_hz
        if sampling_frequency_hz is not None
        else defaults.get("sampling_frequency_hz")
    )
    return resolve_sampling_params(
        measurements_count=count,
        total_duration_seconds=duration,
        sampling_frequency_hz=freq,
    )


def get_ammeter_config(config: Dict[str, Any], ammeter_type: str) -> AmmeterConfig:
    """Return validated AmmeterConfig for a configured ammeter type."""
    key = ammeter_type.strip().lower()
    ammeters = config.get("ammeters", {})
    if key not in ammeters:
        available = ", ".join(sorted(ammeters.keys()))
        raise ValueError(f"Unknown ammeter type {ammeter_type!r}. Available: {available}")

    entry = ammeters[key]
    if not isinstance(entry, dict) or "port" not in entry or "command" not in entry:
        raise ValueError(f"Ammeter '{key}' configuration must define 'port' and 'command'.")
    testing_cfg = config.get("testing", {}) or {}
    cmd = entry["command"]
    command_bytes = cmd.encode("utf-8") if isinstance(cmd, str) else cmd
    return AmmeterConfig(
        name=key,
        port=int(entry["port"]),
        command=command_bytes,
        method=str(entry.get("method", "")),
        host=str(entry.get("host", testing_cfg.get("host", "localhost"))),
        timeout_seconds=float(
            entry.get("timeout_seconds", testing_cfg.get("timeout_seconds", 2.0))
        ),
    )
