from typing import Any, Dict, Iterable, List, Optional

from src.analysis.analyzer import StatisticalAnalyzer
from src.storage.result_manager import ResultManager
from src.testing.ammeter_client import BaseAmmeterClient, TcpAmmeterClient
from src.testing.sampler import CurrentSampler, ErrorSimulator
from src.utils.config import (
    get_ammeter_config,
    get_sampling_config,
    load_config,
)
from src.utils.logger import TestLogger
from src.visualization.visualizer import ResultVisualizer


class AmmeterTestFramework:
    """Unified, configuration-driven framework for testing ammeter emulators."""

    def __init__(
        self,
        config_path: str = "config/config.yaml",
        logger: Optional[TestLogger] = None,
    ):
        self.config_path = config_path
        self.config = load_config(config_path)
        rm_cfg = self.config.get("result_management", {}) or {}
        viz_cfg = (self.config.get("analysis", {}) or {}).get("visualization", {}) or {}
        log_dir = rm_cfg.get("log_dir", "results/logs")
        log_level = rm_cfg.get("log_level", "VERBOSE")
        self.logger = logger or TestLogger(
            "ammeter_framework", log_dir=log_dir, level=log_level
        )
        self.sampler = CurrentSampler()
        self.analyzer = StatisticalAnalyzer()
        self.result_manager = ResultManager(save_dir=rm_cfg.get("save_path", "results/runs"))
        self.visualizer = ResultVisualizer(output_dir=viz_cfg.get("output_dir", "results/plots"))

    @property
    def configured_ammeters(self) -> Iterable[str]:
        return list(self.config.get("ammeters", {}).keys())

    def create_client(self, ammeter_type: str) -> BaseAmmeterClient:
        """Instantiate a config-driven client for the requested ammeter type."""
        ammeter_cfg = get_ammeter_config(self.config, ammeter_type)
        return TcpAmmeterClient(ammeter_cfg)

    def run_test(
        self,
        ammeter_type: str,
        measurements_count: Optional[int] = None,
        total_duration_seconds: Optional[float] = None,
        sampling_frequency_hz: Optional[float] = None,
        include_precision_metrics: Optional[bool] = None,
        error_simulator: Optional[ErrorSimulator] = None,
        fail_fast: bool = False,
        client: Optional[BaseAmmeterClient] = None,
    ) -> Dict[str, Any]:
        """Run a timed sampling test against one ammeter and return a structured result."""
        active_client = client or self.create_client(ammeter_type)
        sampling_cfg = get_sampling_config(
            self.config,
            measurements_count=measurements_count,
            total_duration_seconds=total_duration_seconds,
            sampling_frequency_hz=sampling_frequency_hz,
        )
        if include_precision_metrics is None:
            include_precision_metrics = bool(
                self.config.get("analysis", {}).get("include_precision_metrics", False)
            )

        self.logger.info(
            f"Starting test for '{active_client.name}': "
            f"count={sampling_cfg.measurements_count}, "
            f"duration={sampling_cfg.total_duration_seconds:.3f}s, "
            f"freq={sampling_cfg.sampling_frequency_hz:.2f}Hz"
        )

        sampling_result = self.sampler.collect(
            client=active_client,
            sampling_config=sampling_cfg,
            error_simulator=error_simulator,
            fail_fast=fail_fast,
            logger=self.logger,
        )

        result = sampling_result.to_dict()
        result["include_precision_metrics"] = include_precision_metrics

        if sampling_result.values:
            stats = self.analyzer.analyze(
                sampling_result.values,
                include_precision_metrics=include_precision_metrics,
            )
            result["statistics"] = stats
            if include_precision_metrics:
                cv_display = f"{stats['cv_percent']}%" if stats.get("cv_percent") is not None else "N/A"
                precision_str = (
                    f", cv={cv_display}, iqr={stats['iqr']:.4f}A, "
                    f"ci95=[{stats['ci95_low']:.4f}, {stats['ci95_high']:.4f}]A, "
                    f"rating={stats['consistency_rating']}"
                )
            else:
                precision_str = ""
            self.logger.info(
                f"Stats '{active_client.name}': mean={stats['mean']:.4f}A, "
                f"median={stats['median']:.4f}A, std={stats['std_dev']:.4f}A, "
                f"min={stats['min']:.4f}A, max={stats['max']:.4f}A{precision_str}"
            )
        else:
            result["statistics"] = None
            self.logger.warning(
                f"Stats '{active_client.name}': skipped (0 valid samples collected)."
            )

        self.logger.info(
            f"Completed '{active_client.name}': "
            f"collected={len(sampling_result.samples)}, "
            f"errors={len(sampling_result.errors)}, "
            f"elapsed={sampling_result.actual_duration_seconds:.3f}s"
        )
        return result

    def compare_results(self, results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Compare precision and reliability across multiple ammeter results."""
        comparison = self.analyzer.compare_ammeters(results)
        self.logger.info(comparison["summary"])
        return comparison

    def execute_suite(
        self,
        ammeter_types: Optional[Iterable[str]] = None,
        measurements_count: Optional[int] = None,
        total_duration_seconds: Optional[float] = None,
        sampling_frequency_hz: Optional[float] = None,
        include_precision_metrics: Optional[bool] = None,
        save: bool = True,
        visualize: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run full test suite, compare ammeters, archive JSON results, and generate plots."""
        results = self.run_all(
            ammeter_types=ammeter_types,
            measurements_count=measurements_count,
            total_duration_seconds=total_duration_seconds,
            sampling_frequency_hz=sampling_frequency_hz,
            include_precision_metrics=include_precision_metrics,
        )

        valid_count = sum(1 for r in results.values() if r.get("samples"))
        comparison = self.compare_results(results) if valid_count >= 2 else None

        run_id = self.result_manager.generate_run_id()
        saved_record: Optional[Dict[str, Any]] = None
        if save:
            saved_record = self.result_manager.save_run(
                results=results,
                comparison=comparison,
                metadata=metadata,
                run_id=run_id,
            )
            self.logger.info(f"Saved run '{run_id}' -> {saved_record['file_path']}")

        viz_cfg = (self.config.get("analysis", {}) or {}).get("visualization", {}) or {}
        should_plot = viz_cfg.get("enabled", True) if visualize is None else visualize
        plots: List[str] = []
        if should_plot:
            plots = self.visualizer.generate_plots(
                run_id=run_id,
                results=results,
                comparison=comparison,
                plot_types=viz_cfg.get("plot_types"),
            )
            for plot_path in plots:
                self.logger.info(f"Generated plot -> {plot_path}")

        return {
            "run_id": run_id,
            "results": results,
            "comparison": comparison,
            "saved_path": saved_record["file_path"] if saved_record else None,
            "plots": plots,
        }

    def run_all(
        self,
        ammeter_types: Optional[Iterable[str]] = None,
        measurements_count: Optional[int] = None,
        total_duration_seconds: Optional[float] = None,
        sampling_frequency_hz: Optional[float] = None,
        include_precision_metrics: Optional[bool] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Run sampling tests across all configured (or specified) ammeters."""
        targets = list(ammeter_types) if ammeter_types is not None else list(self.configured_ammeters)
        results: Dict[str, Dict[str, Any]] = {}
        for ammeter_type in targets:
            results[ammeter_type] = self.run_test(
                ammeter_type=ammeter_type,
                measurements_count=measurements_count,
                total_duration_seconds=total_duration_seconds,
                sampling_frequency_hz=sampling_frequency_hz,
                include_precision_metrics=include_precision_metrics,
            )
        return results
