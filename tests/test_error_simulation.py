import pytest

from Ammeters.client import request_current_from_ammeter
from src.testing.ammeter_client import BaseAmmeterClient
from src.testing.sampler import ErrorSimulator
from src.testing.test_framework import AmmeterTestFramework

pytestmark = pytest.mark.negative


class _ConstantMockClient(BaseAmmeterClient):
    def __init__(self, value: float = 10.0):
        super().__init__(name="mock_ammeter", method="Constant Mock")
        self._value = value

    def read_current(self) -> float:
        return self._value


def test_error_simulator_timeout_resilient_collection(
    framework: AmmeterTestFramework,
) -> None:
    sim = ErrorSimulator(failure_rate=1.0, error_mode="timeout", seed=42)
    result = framework.run_test(
        "mock_ammeter",
        measurements_count=4,
        total_duration_seconds=0.1,
        error_simulator=sim,
        client=_ConstantMockClient(),
    )
    assert result["samples_collected"] == 0
    assert result["errors_count"] == 4
    assert result["statistics"] is None
    assert all(e["error_type"] == "TimeoutError" for e in result["errors"])


def test_error_simulator_fail_fast_raises_immediately(
    framework: AmmeterTestFramework,
) -> None:
    sim = ErrorSimulator(failure_rate=1.0, error_mode="connection", seed=1)
    with pytest.raises(ConnectionError, match="Simulated connection reset"):
        framework.run_test(
            "mock_ammeter",
            measurements_count=4,
            total_duration_seconds=0.1,
            error_simulator=sim,
            fail_fast=True,
            client=_ConstantMockClient(),
        )


def test_error_simulator_outlier_injection(framework: AmmeterTestFramework) -> None:
    sim = ErrorSimulator(
        failure_rate=1.0, error_mode="outlier", outlier_multiplier=50.0, seed=7
    )
    result = framework.run_test(
        "mock_ammeter",
        measurements_count=3,
        total_duration_seconds=0.1,
        error_simulator=sim,
        client=_ConstantMockClient(2.0),
    )
    assert result["samples_collected"] == 3
    assert result["statistics"]["mean"] == 100.0


def test_connection_refused_on_closed_port() -> None:
    with pytest.raises(ConnectionError):
        request_current_from_ammeter(
            port=59999, command=b"MEASURE_GREENLEE -get_measurement", timeout=0.5, verbose=False
        )


def test_invalid_command_against_live_greenlee_emulator(greenlee_emulator) -> None:
    with pytest.raises(ValueError, match="Empty response"):
        request_current_from_ammeter(
            port=greenlee_emulator.port,
            command=b"INVALID_CMD",
            timeout=1.0,
            verbose=False,
        )
