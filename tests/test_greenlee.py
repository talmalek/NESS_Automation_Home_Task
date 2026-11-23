import os

import pytest

from src.testing.test_framework import AmmeterTestFramework
from src.visualization.visualizer import ResultVisualizer
from tests.conftest import attach_plot_to_report, attach_text_to_report

pytestmark = pytest.mark.greenlee


@pytest.mark.sanity
def test_greenlee_sanity(greenlee_emulator, framework: AmmeterTestFramework) -> None:
    """Pre-flight check: Greenlee emulator responds with valid Ohm's Law current."""
    client = framework.create_client("greenlee")
    reading = client.read_current()
    assert isinstance(reading, float)
    assert 0.01 <= reading <= 100.0


def test_greenlee_sampling_and_core_stats(
    greenlee_emulator,
    framework: AmmeterTestFramework,
    session_run_id: str,
    session_results: dict,
    request: pytest.FixtureRequest,
) -> None:
    result = framework.run_test(
        "greenlee", measurements_count=8, total_duration_seconds=0.4
    )
    assert result["ammeter_name"] == "greenlee"
    assert result["samples_collected"] == 8
    assert result["errors_count"] == 0

    stats = result["statistics"]
    assert stats is not None
    assert stats["count"] == 8
    assert stats["min"] <= stats["median"] <= stats["max"]
    assert stats["std_dev"] >= 0.0
    assert "cv" not in stats  # Precision metrics are opt-in by default

    session_results["greenlee"] = result
    plots = ResultVisualizer().generate_plots(
        run_id=f"{session_run_id}_greenlee",
        results={"greenlee": result},
        plot_types=("time_series",),
    )
    for path in plots:
        assert os.path.isfile(path)
        attach_plot_to_report(request, path, f"Greenlee Time Series ({session_run_id})")


def test_greenlee_opt_in_precision_metrics(
    greenlee_emulator,
    framework: AmmeterTestFramework,
    session_run_id: str,
    request: pytest.FixtureRequest,
) -> None:
    result = framework.run_test(
        "greenlee",
        measurements_count=8,
        total_duration_seconds=0.4,
        include_precision_metrics=True,
    )
    stats = result["statistics"]
    assert stats is not None
    assert "cv" in stats and "iqr" in stats and "ci95_low" in stats
    assert stats["ci95_low"] <= stats["mean"] <= stats["ci95_high"]

    attach_text_to_report(
        request,
        (
            f"Greenlee Precision Metrics ({session_run_id})\n"
            f"mean={stats['mean']}A | median={stats['median']}A | std_dev={stats['std_dev']}A\n"
            f"CV={stats['cv_percent']}% | IQR={stats['iqr']}A | "
            f"CI95=[{stats['ci95_low']}, {stats['ci95_high']}]A | rating={stats['consistency_rating']}"
        ),
        "Precision Metrics Summary",
    )
    plots = ResultVisualizer().generate_plots(
        run_id=f"{session_run_id}_greenlee_precision",
        results={"greenlee": result},
        plot_types=("time_series", "distribution"),
    )
    for path in plots:
        assert os.path.isfile(path)
        attach_plot_to_report(request, path, os.path.basename(path))
