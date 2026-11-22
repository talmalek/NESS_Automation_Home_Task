import argparse
import json
import threading
import time
from typing import Dict, List, Type

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.base_ammeter import AmmeterEmulatorBase
from src.testing.test_framework import AmmeterTestFramework
from src.utils.config import get_ammeter_config

EMULATOR_CLASSES: Dict[str, Type[AmmeterEmulatorBase]] = {
    "greenlee": GreenleeAmmeter,
    "entes": EntesAmmeter,
    "circutor": CircutorAmmeter,
}


def start_emulators(framework: AmmeterTestFramework, targets: List[str]) -> List[AmmeterEmulatorBase]:
    started: List[AmmeterEmulatorBase] = []
    for name in targets:
        cls = EMULATOR_CLASSES.get(name.lower())
        if cls is None:
            continue
        cfg = get_ammeter_config(framework.config, name)
        emulator = cls(cfg.port)
        threading.Thread(target=emulator.start_server, daemon=True).start()
        started.append(emulator)
    if started:
        time.sleep(0.5)
    return started


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ammeter Testing Framework CLI — run tests, compare history, and generate reports."
    )
    parser.add_argument("--config", default="config/config.yaml", help="Path to YAML config file.")
    parser.add_argument("--ammeters", nargs="+", help="Ammeter names to test (default: all configured).")
    parser.add_argument("--count", type=int, help="Override measurements_count.")
    parser.add_argument("--duration", type=float, help="Override total_duration_seconds.")
    parser.add_argument("--frequency", type=float, help="Override sampling_frequency_hz.")
    parser.add_argument(
        "--precision",
        action="store_true",
        help="Include opt-in calibration/precision metrics (CV, IQR, CI95) per ammeter.",
    )
    parser.add_argument("--log-level", help="Override log level (DEBUG, VERBOSE, INFO, WARNING).")
    parser.add_argument("--no-plots", action="store_true", help="Disable PNG visualization generation.")
    parser.add_argument(
        "--no-start-emulators",
        action="store_true",
        help="Assume emulators are already running externally.",
    )
    parser.add_argument("--list-runs", action="store_true", help="List archived historical test runs.")
    parser.add_argument(
        "--compare-runs",
        nargs=2,
        metavar=("RUN_A", "RUN_B"),
        help="Compare two archived runs by run_id.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    framework = AmmeterTestFramework(config_path=args.config)
    if args.log_level:
        framework.logger.set_level(args.log_level)

    if args.list_runs:
        runs = framework.result_manager.list_runs()
        if not runs:
            print("No archived test runs found.")
            return
        print(f"Archived runs ({len(runs)}):")
        for item in runs:
            print(
                f"  - {item['run_id']} | saved={item['saved_at_utc']} | "
                f"ammeters={','.join(item['ammeters'])} | best={item['most_reliable']}"
            )
        return

    if args.compare_runs:
        diff = framework.result_manager.compare_runs(args.compare_runs[0], args.compare_runs[1])
        print(json.dumps(diff, indent=2))
        return

    targets = args.ammeters or list(framework.configured_ammeters)
    emulators: List[AmmeterEmulatorBase] = []
    if not args.no_start_emulators:
        emulators = start_emulators(framework, targets)

    try:
        outcome = framework.execute_suite(
            ammeter_types=targets,
            measurements_count=args.count,
            total_duration_seconds=args.duration,
            sampling_frequency_hz=args.frequency,
            include_precision_metrics=True if args.precision else None,
            save=True,
            visualize=False if args.no_plots else None,
        )

        print(f"\n=== Test Suite Complete (run_id: {outcome['run_id']}) ===")
        for name, res in outcome["results"].items():
            stats = res.get("statistics")
            if stats:
                print(
                    f"  {name:8s} | n={stats['count']:3d} | mean={stats['mean']:9.4f}A | "
                    f"median={stats['median']:9.4f}A | std={stats['std_dev']:9.4f}A | "
                    f"min={stats['min']:8.4f}A | max={stats['max']:9.4f}A"
                )
        if outcome["comparison"]:
            print(f"\nAccuracy Assessment: {outcome['comparison']['summary']}")
        if outcome["saved_path"]:
            print(f"Archived JSON: {outcome['saved_path']}")
        if outcome["plots"]:
            print("Generated Plots:")
            for plot in outcome["plots"]:
                print(f"  - {plot}")
    finally:
        for emulator in emulators:
            emulator.stop()


if __name__ == "__main__":
    main()
