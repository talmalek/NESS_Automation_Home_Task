import math
import os

import pytest

from src.analysis.analyzer import StatisticalAnalyzer
from src.storage.result_manager import ResultManager
from src.utils.config import resolve_sampling_params
from src.utils.logger import TestLogger
from src.visualization.visualizer import ResultVisualizer

pytestmark = pytest.mark.unit


def test_sampling_resolver_all_two_of_three_pairs() -> None:
    s1 = resolve_sampling_params(measurements_count=20, total_duration_seconds=4.0)
    assert s1.sampling_frequency_hz == 5.0

    s2 = resolve_sampling_params(total_duration_seconds=4.0, sampling_frequency_hz=5.0)
    assert s2.measurements_count == 20

    s3 = resolve_sampling_params(measurements_count=20, sampling_frequency_hz=5.0)
    assert s3.total_duration_seconds == 4.0


def test_sampling_resolver_rejects_conflicts_and_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="Inconsistent"):
        resolve_sampling_params(
            measurements_count=5, total_duration_seconds=2.0, sampling_frequency_hz=10.0
        )
    with pytest.raises(ValueError, match="at least 2"):
        resolve_sampling_params(measurements_count=5)
    with pytest.raises(ValueError, match="positive integer"):
        resolve_sampling_params(measurements_count=0, total_duration_seconds=1.0)


def test_logger_verbose_vs_info_filtering(tmp_path) -> None:
    v_log = TestLogger("unit_verbose", log_dir=str(tmp_path), level="VERBOSE")
    v_log.info("lifecycle event")
    v_log.verbose("sample reading 1.23 A")

    with open(v_log.log_file, "r", encoding="utf-8") as fh:
        v_content = fh.read()
    assert "| INFO" in v_content
    assert "| VERBOSE" in v_content

    i_log = TestLogger("unit_info", log_dir=str(tmp_path), level="INFO")
    i_log.info("lifecycle event")
    i_log.verbose("hidden sample reading")

    with open(i_log.log_file, "r", encoding="utf-8") as fh:
        i_content = fh.read()
    assert "| INFO" in i_content
    assert "| VERBOSE" not in i_content


def test_statistical_analyzer_core_and_precision_metrics() -> None:
    analyzer = StatisticalAnalyzer()
    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    core = analyzer.analyze(values, include_precision_metrics=False)
    assert core["count"] == 5
    assert core["mean"] == 30.0
    assert core["median"] == 30.0
    assert core["min"] == 10.0
    assert core["max"] == 50.0
    assert math.isclose(core["std_dev"], 15.811388, rel_tol=1e-5)
    assert "cv" not in core

    full = analyzer.analyze(values, include_precision_metrics=True)
    assert full["iqr"] == 20.0
    assert math.isclose(full["cv"], 15.811388 / 30.0, rel_tol=1e-4)
    assert full["ci95_low"] < 30.0 < full["ci95_high"]

    with pytest.raises(ValueError):
        analyzer.analyze([])


def test_cross_ammeter_accuracy_ranking() -> None:
    analyzer = StatisticalAnalyzer()
    fake_results = {
        "steady": {
            "ammeter_name": "steady",
            "method": "Stable Method",
            "samples": [{"current_amps": v} for v in [10.0, 10.1, 9.9, 10.0, 10.05]],
        },
        "noisy": {
            "ammeter_name": "noisy",
            "method": "Noisy Method",
            "samples": [{"current_amps": v} for v in [1.0, 50.0, 2.0, 80.0, 5.0]],
        },
    }
    comp = analyzer.compare_ammeters(fake_results)
    assert comp["most_reliable"] == "steady"
    assert comp["ranking"][0]["rank"] == 1
    assert comp["ranking"][0]["ammeter_name"] == "steady"


def test_result_manager_archive_retrieve_and_compare(tmp_path) -> None:
    rm = ResultManager(save_dir=str(tmp_path / "runs"))
    run_a = rm.save_run(
        results={
            "greenlee": {
                "statistics": {"mean": 1.0, "median": 1.0, "std_dev": 0.2},
            }
        }
    )
    run_b = rm.save_run(
        results={
            "greenlee": {
                "statistics": {"mean": 1.5, "median": 1.4, "std_dev": 0.3},
            }
        }
    )

    loaded = rm.load_run(run_a["run_id"])
    assert loaded["run_id"] == run_a["run_id"]
    assert len(rm.list_runs()) == 2

    diff = rm.compare_runs(run_a["run_id"], run_b["run_id"])
    assert diff["ammeter_diffs"]["greenlee"]["mean_delta"] == 0.5
    assert diff["ammeter_diffs"]["greenlee"]["mean_pct_change"] == 50.0

    with pytest.raises(FileNotFoundError):
        rm.load_run("nonexistent_run_id")


def test_visualizer_generates_png_plots(
    session_run_id: str,
    session_results: dict,
    request: pytest.FixtureRequest,
) -> None:
    """Generate real PNG plots from current session or latest archived run_id;
    fall back to clearly labeled virtual/mock data only if no real runs exist."""
    from tests.conftest import attach_plot_to_report, attach_text_to_report

    viz = ResultVisualizer(output_dir="results/plots")
    title_suffix = ""

    if session_results:
        source_run_id = session_run_id
        plot_results = session_results
        source_note = (
            f"Data source: LIVE PYTEST SESSION | run_id={source_run_id} | "
            f"ammeters={', '.join(plot_results.keys())}"
        )
    else:
        rm = ResultManager(save_dir="results/runs")
        archived = rm.list_runs()
        if archived:
            latest = rm.load_run(archived[0]["run_id"])
            source_run_id = latest["run_id"]
            plot_results = latest["results"]
            source_note = (
                f"Data source: LATEST ARCHIVED RUN | run_id={source_run_id} | "
                f"ammeters={', '.join(plot_results.keys())}"
            )
        else:
            source_run_id = f"{session_run_id}_virtual_mock"
            title_suffix = "[VIRTUAL / MOCK DATA]"
            plot_results = {
                "virtual_ammeter": {
                    "ammeter_name": "virtual_ammeter",
                    "method": "Virtual Mock Data (no real run files found)",
                    "samples": [
                        {"elapsed_seconds": 0.0, "current_amps": 1.0},
                        {"elapsed_seconds": 0.1, "current_amps": 1.2},
                        {"elapsed_seconds": 0.2, "current_amps": 0.9},
                    ],
                    "statistics": {"mean": 1.033333},
                }
            }
            source_note = (
                f"Data source: VIRTUAL / MOCK DATA (no real run files found) | "
                f"run_id={source_run_id}"
            )

    comparison = None
    if len(plot_results) >= 2:
        comparison = StatisticalAnalyzer().compare_ammeters(plot_results)
        source_note += f"\nAccuracy Assessment: {comparison['summary']}"

    attach_text_to_report(request, source_note, "Visualizer Data Source")

    plots = viz.generate_plots(
        source_run_id,
        plot_results,
        comparison=comparison,
        title_suffix=title_suffix,
    )
    assert len(plots) >= 2
    for path in plots:
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 0
        attach_plot_to_report(request, path, os.path.basename(path))


@pytest.mark.cleanup
def test_standalone_cleanup_old_reports_and_artifacts() -> None:
    """Standalone maintenance test to prune reports, plots, and runs older than max_reports."""
    from src.utils.config import load_config

    cfg = load_config("config/config.yaml")
    rm_cfg = cfg.get("result_management", {}) or {}
    viz_cfg = (cfg.get("analysis", {}) or {}).get("visualization", {}) or {}
    max_reports = int(rm_cfg.get("max_reports", 10))
    reports_dir = rm_cfg.get("report_dir", "results/reports")
    runs_dir = rm_cfg.get("save_path", "results/runs")
    plots_dir = viz_cfg.get("output_dir", "results/plots")

    logger = TestLogger("artifact_cleanup", level="INFO")
    logger.info(f"Starting standalone artifact cleanup (max_reports={max_reports})...")

    removed = ResultManager.prune_linked_artifacts(
        max_reports=max_reports,
        reports_dir=reports_dir,
        plots_dir=plots_dir,
        runs_dir=runs_dir,
        logger=logger,
    )
    assert set(removed.keys()) == {"reports", "plots", "runs"}

    remaining_reports = [
        f for f in os.listdir(reports_dir)
        if f.endswith(".html") and os.path.isfile(os.path.join(reports_dir, f))
    ] if os.path.isdir(reports_dir) else []

    logger.info(f"Cleanup finished. Remaining reports count: {len(remaining_reports)}")
    assert len(remaining_reports) <= max_reports
