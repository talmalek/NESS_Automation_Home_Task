import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.testing.ammeter_client import BaseAmmeterClient
from src.utils.config import SamplingConfig


@dataclass(frozen=True)
class Sample:
    index: int
    timestamp_iso: str
    elapsed_seconds: float
    current_amps: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SamplingError:
    index: int
    timestamp_iso: str
    error_type: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorSimulator:
    """Optional error injection hook for negative QA testing (disabled by default)."""

    failure_rate: float = 0.0
    error_mode: str = "timeout"  # timeout | connection | invalid_payload | outlier
    outlier_multiplier: float = 100.0
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def should_trigger(self) -> bool:
        return self.failure_rate > 0.0 and self._rng.random() < self.failure_rate

    def maybe_inject_before_read(self) -> None:
        if not self.should_trigger():
            return
        if self.error_mode == "timeout":
            raise TimeoutError("Simulated socket timeout.")
        if self.error_mode == "connection":
            raise ConnectionError("Simulated connection reset by peer.")
        if self.error_mode == "invalid_payload":
            raise ValueError("Simulated malformed numeric payload.")

    def maybe_transform_value(self, value: float) -> float:
        if self.error_mode == "outlier" and self.should_trigger():
            return value * self.outlier_multiplier
        return value


@dataclass
class SamplingResult:
    ammeter_name: str
    method: str
    sampling_config: SamplingConfig
    samples: List[Sample] = field(default_factory=list)
    errors: List[SamplingError] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    actual_duration_seconds: float = 0.0

    @property
    def values(self) -> List[float]:
        return [s.current_amps for s in self.samples]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ammeter_name": self.ammeter_name,
            "method": self.method,
            "sampling_config": self.sampling_config.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "actual_duration_seconds": round(self.actual_duration_seconds, 6),
            "samples_collected": len(self.samples),
            "errors_count": len(self.errors),
            "samples": [s.to_dict() for s in self.samples],
            "errors": [e.to_dict() for e in self.errors],
        }


class CurrentSampler:
    """Collects drift-compensated current samples from any BaseAmmeterClient."""

    def collect(
        self,
        client: BaseAmmeterClient,
        sampling_config: SamplingConfig,
        error_simulator: Optional[ErrorSimulator] = None,
        fail_fast: bool = False,
        logger: Optional[Any] = None,
    ) -> SamplingResult:
        interval = sampling_config.interval_seconds
        count = sampling_config.measurements_count

        samples: List[Sample] = []
        errors: List[SamplingError] = []

        started_at = datetime.now(timezone.utc).isoformat()
        start_perf = time.perf_counter()

        for idx in range(count):
            target_time = start_perf + idx * interval
            sleep_for = target_time - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)

            now_iso = datetime.now(timezone.utc).isoformat()
            elapsed = time.perf_counter() - start_perf

            try:
                if error_simulator is not None:
                    error_simulator.maybe_inject_before_read()
                value = client.read_current()
                if error_simulator is not None:
                    value = error_simulator.maybe_transform_value(value)
                samples.append(
                    Sample(
                        index=idx,
                        timestamp_iso=now_iso,
                        elapsed_seconds=round(elapsed, 6),
                        current_amps=value,
                    )
                )
                if logger is not None:
                    logger.verbose(
                        f"[{client.name}] Sample {idx + 1}/{count} | "
                        f"elapsed={elapsed:.3f}s | current={value:.6f} A"
                    )
            except Exception as exc:
                if logger is not None:
                    logger.warning(
                        f"[{client.name}] Sample {idx + 1}/{count} FAILED | "
                        f"{type(exc).__name__}: {exc}"
                    )
                if fail_fast:
                    raise
                errors.append(
                    SamplingError(
                        index=idx,
                        timestamp_iso=now_iso,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )

        actual_duration = time.perf_counter() - start_perf
        completed_at = datetime.now(timezone.utc).isoformat()

        return SamplingResult(
            ammeter_name=client.name,
            method=client.method,
            sampling_config=sampling_config,
            samples=samples,
            errors=errors,
            started_at=started_at,
            completed_at=completed_at,
            actual_duration_seconds=actual_duration,
        )
