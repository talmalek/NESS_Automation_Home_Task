import os

import pytest

from src.testing.test_framework import AmmeterTestFramework
from src.visualization.visualizer import ResultVisualizer
from tests.conftest import attach_plot_to_report, attach_text_to_report

pytestmark = pytest.mark.entes


@pytest.mark.sanity
def test_entes_sanity(entes_emulator, framework: AmmeterTestFramework) -> None:
    """Pre-flight check: ENTES emulator responds with valid Hall Effect current."""
    client = framework.create_client("entes")
    reading = client.read_current()
    assert isinstance(reading, float)
    assert 5.0 <= reading <= 200.0


def test_entes_sampling_and_core_stats(
    entes_emulator,
    framework: AmmeterTestFramework,
    session_run_id: str,
    session_results: dict,
    request: pytest.FixtureRequest,
) -> None:
    result = framework.run_test(
        "entes", measurements_count=8, total_duration_seconds=0.4
    )
    assert result["ammeter_name"] == "entes"
    assert result["samples_collected"] == 8
    assert result["errors_count"] == 0

    stats = result["statistics"]
    assert stats is not None
    assert stats["count"] == 8
    assert 5.0 <= stats["min"] <= stats["max"] <= 200.0
    assert "cv" not in stats

    session_results["entes"] = result
    plots = ResultVisualizer().generate_plots(
        run_id=f"{session_run_id}_entes",
        results={"entes": result},
        plot_types=("time_series",),
    )
    for path in plots:
        assert os.path.isfile(path)
        attach_plot_to_report(request, path, f"ENTES Time Series ({session_run_id})")


def test_entes_opt_in_precision_metrics(
    entes_emulator,
    framework: AmmeterTestFramework,
    session_run_id: str,
    request: pytest.FixtureRequest,
) -> None:
    result = framework.run_test(
        "entes",
        measurements_count=8,
        total_duration_seconds=0.4,
        include_precision_metrics=True,
    )
    stats = result["statistics"]
    assert stats is not None
    assert "cv" in stats and "iqr" in stats and "ci95_high" in stats
    assert stats["ci95_low"] <= stats["mean"] <= stats["ci95_high"]

    attach_text_to_report(
        request,
        (
            f"ENTES Precision Metrics ({session_run_id})\n"
            f"mean={stats['mean']}A | median={stats['median']}A | std_dev={stats['std_dev']}A\n"
            f"CV={stats['cv_percent']}% | IQR={stats['iqr']}A | "
            f"CI95=[{stats['ci95_low']}, {stats['ci95_high']}]A | rating={stats['consistency_rating']}"
        ),
        "Precision Metrics Summary",
    )
    plots = ResultVisualizer().generate_plots(
        run_id=f"{session_run_id}_entes_precision",
        results={"entes": result},
        plot_types=("time_series", "distribution"),
    )
    for path in plots:
        assert os.path.isfile(path)
        attach_plot_to_report(request, path, os.path.basename(path))
