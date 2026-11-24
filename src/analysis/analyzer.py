import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

# Two-sided 95% Student-t critical values (df = n - 1). Source: standard t-table.
_T95: Dict[int, float] = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
    27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980,
}


def _t_critical_95(df: int) -> float:
    """Return two-sided 95% Student-t critical value (conservative for intermediate df)."""
    if df >= 120:
        return 1.960 if df > 1000 else _T95[120]
    return _T95[max(k for k in _T95 if k <= df)]


class StatisticalAnalyzer:
    """Shared statistical engine for all ammeter types (zero per-ammeter duplication).

    Computes core metrics (mean, median, std_dev, min, max) by default.
    Opt-in precision/calibration metrics (CV, IQR, CI95) are computed only when
    include_precision_metrics=True or during cross-ammeter comparison.
    """

    def analyze(
        self,
        values: Sequence[float],
        include_precision_metrics: bool = False,
    ) -> Dict[str, Any]:
        if not values:
            raise ValueError("Cannot compute statistics on an empty sample list.")

        arr = np.asarray(values, dtype=float)
        n = int(arr.size)
        mean_val = float(np.mean(arr))
        median_val = float(np.median(arr))
        std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))

        metrics: Dict[str, Any] = {
            "count": n,
            "mean": round(mean_val, 6),
            "median": round(median_val, 6),
            "std_dev": round(std_val, 6),
            "min": round(min_val, 6),
            "max": round(max_val, 6),
        }

        if include_precision_metrics:
            metrics.update(self._compute_precision_metrics(arr, mean_val, std_val))

        return metrics

    @staticmethod
    def _compute_precision_metrics(
        arr: np.ndarray, mean_val: float, std_val: float
    ) -> Dict[str, Any]:
        n = int(arr.size)
        cv: Optional[float] = None
        cv_percent: Optional[float] = None
        if abs(mean_val) > 1e-12:
            cv = std_val / abs(mean_val)
            cv_percent = cv * 100.0

        q1, q3 = np.percentile(arr, [25, 75])
        iqr = float(q3 - q1)

        if n > 1 and std_val > 0.0:
            t_crit = _t_critical_95(n - 1)
            margin = t_crit * (std_val / math.sqrt(n))
        else:
            margin = 0.0

        if cv is None:
            rating = "unknown"
        elif cv < 0.25:
            rating = "high"
        elif cv < 0.60:
            rating = "moderate"
        else:
            rating = "low"

        return {
            "cv": round(cv, 6) if cv is not None else None,
            "cv_percent": round(cv_percent, 2) if cv_percent is not None else None,
            "iqr": round(iqr, 6),
            "ci95_margin": round(margin, 6),
            "ci95_low": round(mean_val - margin, 6),
            "ci95_high": round(mean_val + margin, 6),
            "consistency_rating": rating,
        }

    def compare_ammeters(self, results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Compare reliability and precision across multiple ammeter test results.

        Ranks by reading success rate descending first, then scale-independent
        Coefficient of Variation (CV = std_dev / mean) ascending so ammeters
        operating on different current ranges can be compared fairly.
        """
        entries: List[Dict[str, Any]] = []

        for name, res in results.items():
            samples = res.get("samples", [])
            errors_count = int(res.get("errors_count", 0))
            values = [float(s["current_amps"]) for s in samples]
            if not values:
                continue
            attempts = len(values) + errors_count
            success_rate = len(values) / attempts
            stats = self.analyze(values, include_precision_metrics=True)
            entries.append(
                {
                    "ammeter_name": res.get("ammeter_name", name),
                    "method": res.get("method", ""),
                    "samples_count": stats["count"],
                    "errors_count": errors_count,
                    "success_rate": round(success_rate, 4),
                    "mean": stats["mean"],
                    "median": stats["median"],
                    "std_dev": stats["std_dev"],
                    "cv": stats["cv"],
                    "cv_percent": stats["cv_percent"],
                    "iqr": stats["iqr"],
                    "ci95_low": stats["ci95_low"],
                    "ci95_high": stats["ci95_high"],
                    "consistency_rating": stats["consistency_rating"],
                }
            )

        if not entries:
            raise ValueError("No valid ammeter samples available for comparison.")

        entries.sort(
            key=lambda item: (
                -item["success_rate"],
                item["cv"] is None,
                item["cv"] if item["cv"] is not None else float("inf"),
            )
        )
        for rank, item in enumerate(entries, start=1):
            item["rank"] = rank

        best = entries[0]
        summary = (
            f"Most reliable ammeter: '{best['ammeter_name']}' "
            f"({best['method'] or 'N/A'}) — success={best['success_rate'] * 100:.1f}%, "
            f"CV={best['cv_percent']}% (mean={best['mean']} A, std={best['std_dev']} A)."
        )

        return {
            "metric_used": "success_rate desc, then coefficient_of_variation asc",
            "most_reliable": best["ammeter_name"],
            "ranking": entries,
            "summary": summary,
        }
