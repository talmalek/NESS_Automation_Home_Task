import os
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Type

import pytest

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.base_ammeter import AmmeterEmulatorBase
from src.analysis.analyzer import StatisticalAnalyzer
from src.storage.result_manager import ResultManager
from src.testing.test_framework import AmmeterTestFramework
from src.utils.config import get_ammeter_config, load_config
from src.utils.logger import TestLogger


def _load_result_mgmt_cfg() -> Dict[str, Any]:
    try:
        return load_config("config/config.yaml").get("result_management", {}) or {}
    except Exception:
        return {}


def pytest_configure(config: pytest.Config) -> None:
    """Assign a unique run_id and per-run HTML1 report path; enforce retention."""
    rm_cfg = _load_result_mgmt_cfg()
    report_dir = rm_cfg.get("report_dir", "results/reports")
    os.makedirs(report_dir, exist_ok=True)

    run_id = ResultManager.generate_run_id(prefix="pytest")
    config._ammeter_run_id = run_id  # type: ignore[attr-defined]
    config._ammeter_report_dir = report_dir  # type: ignore[attr-defined]
    config._ammeter_max_reports = int(rm_cfg.get("max_reports", 10))  # type: ignore[attr-defined]
    config._ammeter_session_results = {}  # type: ignore[attr-defined]

    # Dynamically set unique HTML1 report filename unless caller explicitly passed --report
    existing_reports = getattr(config.option, "report", None)
    if not existing_reports:
        report_path = os.path.join(report_dir, f"report_{run_id}.html")
        config.option.report = [report_path]


def pytest_collection_modifyitems(items: List[pytest.Item]) -> None:
    """Ensure the combined visualizer report test always runs last in the session."""
    items.sort(key=lambda item: 1 if "visualizer" in item.name else 0)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator:
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        extras = getattr(item, "_html_extras", [])
        if extras:
            report.extras = getattr(report, "extras", []) + extras


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Archive real session results (if any) and enforce max_reports retention."""
    cfg = session.config
    run_id = getattr(cfg, "_ammeter_run_id", None)
    report_dir = getattr(cfg, "_ammeter_report_dir", "results/reports")
    max_reports = getattr(cfg, "_ammeter_max_reports", 10)
    session_results: Dict[str, Dict[str, Any]] = getattr(cfg, "_ammeter_session_results", {})

    if run_id and session_results:
        rm_cfg = _load_result_mgmt_cfg()
        rm = ResultManager(
            save_dir=rm_cfg.get("save_path", "results/runs"),
            max_runs=max_reports,
        )
        comparison = None
        if len(session_results) >= 2:
            comparison = StatisticalAnalyzer().compare_ammeters(session_results)
        rm.save_run(
            results=session_results,
            comparison=comparison,
            metadata={"source": "pytest_session"},
            run_id=run_id,
        )

    ResultManager.prune_old_files(report_dir, max_reports, suffix=".html")


def attach_plot_to_report(request: pytest.FixtureRequest, png_path: str, name: str) -> None:
    """Embed a PNG plot directly inside the self-contained HTML1 report."""
    png_bytes = Path(png_path).read_bytes()
    extras = getattr(request.node, "_html_extras", [])
    extras.append(
        {
            "name": name,
            "format_type": "image",
            "content": png_bytes,
            "extension": "png",
        }
    )
    request.node._html_extras = extras  # type: ignore[attr-defined]


def attach_text_to_report(request: pytest.FixtureRequest, text: str, name: str) -> None:
    """Attach structured text details directly inside the HTML1 report."""
    extras = getattr(request.node, "_html_extras", [])
    extras.append(
        {
            "name": name,
            "format_type": "text",
            "content": text,
        }
    )
    request.node._html_extras = extras  # type: ignore[attr-defined]


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
def session_run_id(request: pytest.FixtureRequest) -> str:
    return getattr(request.config, "_ammeter_run_id", ResultManager.generate_run_id("pytest"))


@pytest.fixture(scope="session")
def session_results(request: pytest.FixtureRequest) -> Dict[str, Dict[str, Any]]:
    return getattr(request.config, "_ammeter_session_results", {})


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
