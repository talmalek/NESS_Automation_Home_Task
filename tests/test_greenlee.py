import pytest

from src.testing.test_framework import AmmeterTestFramework

pytestmark = pytest.mark.greenlee


@pytest.mark.sanity
def test_greenlee_sanity(greenlee_emulator, framework: AmmeterTestFramework) -> None:
    """Pre-flight check: Greenlee emulator responds with valid Ohm's Law current."""
    client = framework.create_client("greenlee")
    reading = client.read_current()
    assert isinstance(reading, float)
    assert 0.01 <= reading <= 100.0


def test_greenlee_sampling_and_core_stats(
    greenlee_emulator, framework: AmmeterTestFramework
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


def test_greenlee_opt_in_precision_metrics(
    greenlee_emulator, framework: AmmeterTestFramework
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
