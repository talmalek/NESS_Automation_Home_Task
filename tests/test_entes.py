import pytest

from src.testing.test_framework import AmmeterTestFramework

pytestmark = pytest.mark.entes


@pytest.mark.sanity
def test_entes_sanity(entes_emulator, framework: AmmeterTestFramework) -> None:
    """Pre-flight check: ENTES emulator responds with valid Hall Effect current."""
    client = framework.create_client("entes")
    reading = client.read_current()
    assert isinstance(reading, float)
    assert 5.0 <= reading <= 200.0


def test_entes_sampling_and_core_stats(
    entes_emulator, framework: AmmeterTestFramework
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


def test_entes_opt_in_precision_metrics(
    entes_emulator, framework: AmmeterTestFramework
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
