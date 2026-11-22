import socket
import threading
import time
from typing import Generator, Type

import pytest

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.base_ammeter import AmmeterEmulatorBase
from src.testing.test_framework import AmmeterTestFramework
from src.utils.config import get_ammeter_config, load_config
from src.utils.logger import TestLogger


def _wait_for_port(port: int, host: str = "localhost", timeout: float = 3.0) -> None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((host, port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError(f"Emulator did not open port {port} within {timeout}s")


def _run_emulator_fixture(
    emulator_cls: Type[AmmeterEmulatorBase], ammeter_name: str
) -> Generator[AmmeterEmulatorBase, None, None]:
    cfg = get_ammeter_config(load_config("config/config.yaml"), ammeter_name)
    emulator = emulator_cls(cfg.port)
    thread = threading.Thread(target=emulator.start_server, daemon=True)
    thread.start()
    _wait_for_port(cfg.port, cfg.host)
    try:
        yield emulator
    finally:
        emulator.stop()
        thread.join(timeout=1.0)


@pytest.fixture(scope="session")
def greenlee_emulator() -> Generator[GreenleeAmmeter, None, None]:
    yield from _run_emulator_fixture(GreenleeAmmeter, "greenlee")


@pytest.fixture(scope="session")
def entes_emulator() -> Generator[EntesAmmeter, None, None]:
    yield from _run_emulator_fixture(EntesAmmeter, "entes")


@pytest.fixture(scope="session")
def circutor_emulator() -> Generator[CircutorAmmeter, None, None]:
    yield from _run_emulator_fixture(CircutorAmmeter, "circutor")


@pytest.fixture
def framework(tmp_path) -> AmmeterTestFramework:
    logger = TestLogger("pytest_framework", log_dir=str(tmp_path / "logs"), level="VERBOSE")
    return AmmeterTestFramework(config_path="config/config.yaml", logger=logger)
