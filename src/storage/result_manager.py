import json
import os
import platform
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ResultManager:
    """Manages unique Run IDs, JSON persistence, historical retrieval, retention, and diffing."""

    def __init__(self, save_dir: str = "results/runs", max_runs: Optional[int] = None):
        self.save_dir = save_dir
        self.max_runs = max_runs
        os.makedirs(self.save_dir, exist_ok=True)

    @staticmethod
    def prune_old_files(directory: str, max_files: int, suffix: str = "") -> List[str]:
        """Keep only the `max_files` most recently modified files matching `suffix`."""
        if max_files <= 0 or not os.path.isdir(directory):
            return []
        candidates = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if (not suffix or f.endswith(suffix))
            and os.path.isfile(os.path.join(directory, f))
        ]
        candidates.sort(key=lambda p: (os.path.getmtime(p), p), reverse=True)
        removed: List[str] = []
        for old_path in candidates[max_files:]:
            try:
                os.remove(old_path)
                removed.append(old_path)
            except OSError:
                continue
        return removed

    @staticmethod
    def generate_run_id(prefix: str = "run") -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        short_id = uuid.uuid4().hex[:8]
        return f"{prefix}_{ts}_{short_id}"

    def _run_path(self, run_id: str) -> str:
        safe_id = os.path.basename(run_id)
        if not safe_id.endswith(".json"):
            safe_id = f"{safe_id}.json"
        return os.path.join(self.save_dir, safe_id)

    def save_run(
        self,
        results: Dict[str, Dict[str, Any]],
        comparison: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist a test run with metadata, samples, statistics, and optional comparison."""
        os.makedirs(self.save_dir, exist_ok=True)
        resolved_id = run_id or self.generate_run_id()
        saved_at = datetime.now(timezone.utc).isoformat()

        run_metadata: Dict[str, Any] = {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "ammeters_tested": list(results.keys()),
        }
        if metadata:
            run_metadata.update(metadata)

        payload: Dict[str, Any] = {
            "run_id": resolved_id,
            "saved_at_utc": saved_at,
            "metadata": run_metadata,
            "results": results,
            "comparison": comparison,
        }

        file_path = self._run_path(resolved_id)
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

        if self.max_runs is not None:
            self.prune_old_files(self.save_dir, self.max_runs, suffix=".json")

        payload["file_path"] = file_path
        return payload

    def load_run(self, run_id: str) -> Dict[str, Any]:
        """Load an archived test run by run_id."""
        file_path = self._run_path(run_id)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Test run '{run_id}' not found at {file_path}")
        with open(file_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def list_runs(self) -> List[Dict[str, Any]]:
        """List all archived test runs sorted newest-first."""
        if not os.path.isdir(self.save_dir):
            return []

        summaries: List[Dict[str, Any]] = []
        for fname in sorted(os.listdir(self.save_dir), reverse=True):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.save_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                summaries.append(
                    {
                        "run_id": data.get("run_id", fname[:-5]),
                        "saved_at_utc": data.get("saved_at_utc", ""),
                        "ammeters": data.get("metadata", {}).get("ammeters_tested", []),
                        "most_reliable": (data.get("comparison") or {}).get("most_reliable"),
                        "file_path": fpath,
                    }
                )
            except (OSError, json.JSONDecodeError):
                continue

        summaries.sort(key=lambda item: item.get("saved_at_utc", ""), reverse=True)
        return summaries

    def compare_runs(self, run_id_a: str, run_id_b: str) -> Dict[str, Any]:
        """Compare statistical metrics between two historical runs for shared ammeters."""
        run_a = self.load_run(run_id_a)
        run_b = self.load_run(run_id_b)

        results_a = run_a.get("results", {})
        results_b = run_b.get("results", {})
        shared = sorted(set(results_a.keys()) & set(results_b.keys()))

        diffs: Dict[str, Dict[str, Any]] = {}
        for name in shared:
            stats_a = results_a[name].get("statistics") or {}
            stats_b = results_b[name].get("statistics") or {}
            if not stats_a or not stats_b:
                continue

            mean_a = float(stats_a["mean"])
            mean_b = float(stats_b["mean"])
            mean_delta = mean_b - mean_a
            mean_pct = (mean_delta / abs(mean_a) * 100.0) if abs(mean_a) > 1e-12 else None

            diffs[name] = {
                "run_a_mean": mean_a,
                "run_b_mean": mean_b,
                "mean_delta": round(mean_delta, 6),
                "mean_pct_change": round(mean_pct, 2) if mean_pct is not None else None,
                "run_a_std_dev": float(stats_a["std_dev"]),
                "run_b_std_dev": float(stats_b["std_dev"]),
                "std_dev_delta": round(float(stats_b["std_dev"]) - float(stats_a["std_dev"]), 6),
                "median_delta": round(float(stats_b["median"]) - float(stats_a["median"]), 6),
            }

        return {
            "run_id_a": run_a.get("run_id", run_id_a),
            "run_id_b": run_b.get("run_id", run_id_b),
            "shared_ammeters": shared,
            "ammeter_diffs": diffs,
        }
