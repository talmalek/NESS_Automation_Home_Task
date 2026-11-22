import os
from typing import Any, Dict, Iterable, List, Optional

import matplotlib

matplotlib.use("Agg")  # Headless backend for cross-platform & CI compatibility
import matplotlib.pyplot as plt


class ResultVisualizer:
    """Generates headless PNG visual reports for ammeter measurement runs."""

    DEFAULT_PLOT_TYPES = ("time_series", "distribution", "summary_comparison")

    def __init__(self, output_dir: str = "results/plots"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_plots(
        self,
        run_id: str,
        results: Dict[str, Dict[str, Any]],
        comparison: Optional[Dict[str, Any]] = None,
        plot_types: Optional[Iterable[str]] = None,
    ) -> List[str]:
        os.makedirs(self.output_dir, exist_ok=True)
        requested = list(plot_types) if plot_types is not None else list(self.DEFAULT_PLOT_TYPES)
        created: List[str] = []

        valid_results = {
            name: res for name, res in results.items() if res.get("samples")
        }
        if not valid_results:
            return created

        if "time_series" in requested:
            created.append(self._plot_time_series(run_id, valid_results))
        if "distribution" in requested:
            created.append(self._plot_distribution(run_id, valid_results))
        if "summary_comparison" in requested and comparison and comparison.get("ranking"):
            created.append(self._plot_summary_comparison(run_id, comparison))

        return created

    def _plot_time_series(self, run_id: str, results: Dict[str, Dict[str, Any]]) -> str:
        n = len(results)
        fig, axes = plt.subplots(n, 1, figsize=(10, 3.2 * n), sharex=False)
        if n == 1:
            axes = [axes]

        for ax, (name, res) in zip(axes, results.items()):
            samples = res["samples"]
            times = [s["elapsed_seconds"] for s in samples]
            vals = [s["current_amps"] for s in samples]
            stats = res.get("statistics") or {}

            ax.plot(times, vals, marker="o", markersize=4, linewidth=1.5, label="Measured Current (A)")
            if "mean" in stats:
                ax.axhline(
                    stats["mean"],
                    color="crimson",
                    linestyle="--",
                    linewidth=1.2,
                    label=f"Mean ({stats['mean']:.4f} A)",
                )
            method = res.get("method", "")
            title = f"{name.upper()} — {method}" if method else name.upper()
            ax.set_title(title)
            ax.set_xlabel("Elapsed Time (s)")
            ax.set_ylabel("Current (A)")
            ax.grid(True, alpha=0.3)
            ax.legend(loc="upper right", fontsize=8)

        fig.suptitle(f"Current Measurements Time Series ({run_id})", fontsize=12, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.96))

        out_path = os.path.join(self.output_dir, f"{run_id}_time_series.png")
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        return out_path

    def _plot_distribution(self, run_id: str, results: Dict[str, Dict[str, Any]]) -> str:
        n = len(results)
        fig, axes = plt.subplots(1, n, figsize=(4.5 * n, 4.2))
        if n == 1:
            axes = [axes]

        for ax, (name, res) in zip(axes, results.items()):
            vals = [s["current_amps"] for s in res["samples"]]
            ax.boxplot(vals, patch_artist=True, boxprops={"facecolor": "#4C72B0", "alpha": 0.6})
            ax.set_title(name.upper())
            ax.set_ylabel("Current (A)")
            ax.set_xticks([])
            ax.grid(True, axis="y", alpha=0.3)

        fig.suptitle(f"Current Distribution per Ammeter ({run_id})", fontsize=12, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.94))

        out_path = os.path.join(self.output_dir, f"{run_id}_distribution.png")
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        return out_path

    def _plot_summary_comparison(self, run_id: str, comparison: Dict[str, Any]) -> str:
        ranking = comparison["ranking"]
        names = [r["ammeter_name"].upper() for r in ranking]
        cvs = [r["cv_percent"] if r["cv_percent"] is not None else 0.0 for r in ranking]
        colors = ["#2ca02c" if i == 0 else "#4C72B0" for i in range(len(names))]

        fig, ax = plt.subplots(figsize=(8, 4.2))
        bars = ax.bar(names, cvs, color=colors, alpha=0.85, edgecolor="black")
        for bar, cv_val in zip(bars, cvs):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height() + 1.0,
                f"{cv_val:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

        ax.set_title(f"Relative Precision Comparison — CV% (Lower is Better) ({run_id})")
        ax.set_ylabel("Coefficient of Variation (%)")
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()

        out_path = os.path.join(self.output_dir, f"{run_id}_summary_comparison.png")
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        return out_path
