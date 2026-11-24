import socket
import threading
from contextlib import contextmanager
from typing import Iterator

import pytest

from Ammeters.client import request_current_from_ammeter
from src.testing.ammeter_client import BaseAmmeterClient
from src.testing.sampler import ErrorSimulator
from src.testing.test_framework import AmmeterTestFramework
from tests.conftest import log_test_step

pytestmark = pytest.mark.negative


@contextmanager
def _silent_server() -> Iterator[int]:
    """Accepts TCP connections via backlog but never replies -> client recv() times out."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind(("localhost", 0))
        srv.listen(1)
        yield srv.getsockname()[1]


@contextmanager
def _reply_server(payload: bytes) -> Iterator[int]:
    """Replies once with a fixed payload to exercise real client parsing paths."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("localhost", 0))
    srv.listen(1)
    srv.settimeout(2.0)

    def _serve() -> None:
        try:
            conn, _ = srv.accept()
            with conn:
                conn.recv(1024)
                conn.sendall(payload)
        except OSError:
            pass

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    try:
        yield srv.getsockname()[1]
    finally:
        thread.join(timeout=2.0)
        srv.close()


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


def test_error_simulator_invalid_payload_and_validation(
    framework: AmmeterTestFramework,
) -> None:
    sim = ErrorSimulator(failure_rate=1.0, error_mode="invalid_payload", seed=3)
    result = framework.run_test(
        "mock_ammeter",
        measurements_count=2,
        total_duration_seconds=0.05,
        error_simulator=sim,
        client=_ConstantMockClient(),
    )
    assert result["samples_collected"] == 0
    assert result["errors_count"] == 2
    assert all(e["error_type"] == "ValueError" for e in result["errors"])

    with pytest.raises(ValueError, match="failure_rate"):
        ErrorSimulator(failure_rate=1.5)
    with pytest.raises(ValueError, match="Invalid error_mode"):
        ErrorSimulator(failure_rate=0.5, error_mode="unknown_mode")


def test_real_socket_timeout_raises_timeout_error() -> None:
    with _silent_server() as port:
        log_test_step(
            f"Connecting to silent TCP server at localhost:{port} (timeout=0.3s); expecting TimeoutError."
        )
        with pytest.raises(TimeoutError, match="Timed out") as exc_info:
            request_current_from_ammeter(port=port, command=b"ANY", timeout=0.3, verbose=False)
        log_test_step(f"Verified expected TimeoutError: {exc_info.value}")


def test_real_socket_non_numeric_payload_raises_value_error() -> None:
    payload = b"ERR:OVERLOAD"
    with _reply_server(payload) as port:
        log_test_step(
            f"Sending command to stub TCP server at localhost:{port} replying {payload!r}; expecting ValueError."
        )
        with pytest.raises(ValueError, match="Invalid numeric payload") as exc_info:
            request_current_from_ammeter(port=port, command=b"ANY", timeout=1.0, verbose=False)
        log_test_step(f"Verified expected ValueError: {exc_info.value}")
