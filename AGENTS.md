# Project Memory & Rules — Ammeter Testing Framework (NESS Home Task)

> Read this file at the start of every session. It defines strict project boundaries, architecture decisions, and current progress.

## 1. Strict Boundaries (Do NOT Violate)
- **Read-Only Vendor Deliverables (NEVER MODIFY)**:
  - `Ammeters/Greenlee_Ammeter.py`
  - `Ammeters/Entes_Ammeter.py`
  - `Ammeters/Circutor_Ammeter.py`
  - `Exam/ammeter-test-specification.md` & `.pdf`
- **Minimal Infrastructure Fixes Only (Document Every Change)**:
  - `Ammeters/base_ammeter.py` (`SO_REUSEADDR` + graceful `stop()`).
  - `Ammeters/client.py` (return `float`, socket timeout, error handling).
  - `main.py` (fix commands/ports so starter script works per spec).
- **Principle — KISS**: Fulfill core + bonus requirements cleanly. No over-engineering, no extra web frameworks. (Optional HTML debug UI is out of scope for now.)
- **Gate-by-Gate Workflow**: Complete ONE gate at a time, verify it works, confirm no unintended changes, then wait for user approval before the next gate.

## 2. Core Architecture (OOP, KISS & Scalable)
- **Config-Driven OOP Ammeter Client (`src/testing/ammeter_client.py`)**:
  - `BaseAmmeterClient` (ABC) defines the standard contract (`read_current() -> float`, `name`, `method`).
  - Single `TcpAmmeterClient(BaseAmmeterClient)` driven by `config/config.yaml` handles Greenlee, ENTES, CIRCUTOR, and any future TCP ammeter with **zero new Python files** (no redundant per-ammeter boilerplate).
  - Non-TCP or custom-payload ammeters can subclass `BaseAmmeterClient` cleanly without changing framework or analysis code.
- **Shared Analytics (`src/analysis/`)**:
  - `StatisticalAnalyzer` computes core metrics (`mean`, `median`, `std_dev`, `min`, `max`) by default, and opt-in precision metrics (`CV`, `IQR`, `CI95`) only when `include_precision_metrics=True` (for calibration / cross-ammeter accuracy ranking, zero duplication).
- **Sampling (`src/testing/sampler.py`)**:
  - Supports any 2-of-3 of (`measurements_count`, `total_duration_seconds`, `sampling_frequency_hz`) and validates consistency if all 3 are provided.
  - Uses `time.perf_counter()` drift-compensated scheduling.
  - Supports configurable error simulation for negative QA tests.
- **Result Management (`src/storage/result_manager.py`)**:
  - Unique `run_id`, JSON persistence with metadata + raw samples + stats, historical retrieval & comparison.
- **Visualization (`src/visualization/visualizer.py`)**:
  - Headless `matplotlib` (`Agg`) PNG reports under `results/plots/`.
- **Structured Logging (`src/utils/logger.py`)**:
  - Never mix emulator `stdout` prints into framework logs (strict SUT vs. Framework separation).
  - Custom `VERBOSE` level (`15`) logs every individual sample reading (`elapsed`, `current_amps`); controlled by `result_management.log_level` in `config/config.yaml` (default `VERBOSE` in dev/QA, switchable to `INFO` in production).
- **Testing & CI**:
  - `pytest` suite under `tests/`.
  - GitHub Actions workflow under `.github/workflows/ci.yml` for Public GitHub submission.

## 3. Environment Notes
- Local Python: `3.9.6` (keep code Python 3.9+ compatible).
- Virtual environment: `.venv/` (excluded from git via `.gitignore`).
- Default ports: `5001` (Greenlee), `5002` (ENTES), `5003` (CIRCUTOR) — avoids macOS `ControlCenter` conflict on port `5000`.
- Exact emulator commands:
  - Greenlee: `MEASURE_GREENLEE -get_measurement`
  - ENTES: `MEASURE_ENTES -get_data`
  - CIRCUTOR: `MEASURE_CIRCUTOR -get_measurement -current`

## 4. Gate Progress Tracker
- [x] **Gate 1**: `.venv` setup, minimal starter fixes (`main.py`, `base_ammeter.py`, `client.py`, `logger.py`), `config/config.yaml`, live verification of all 3 emulators.
- [x] **Gate 2**: `config.py` validation + 2-of-3 sampling, `ammeter_client.py` (`BaseAmmeterClient` + `TcpAmmeterClient`), `sampler.py`, `AmmeterTestFramework`.
- [x] **Gate 3**: `StatisticalAnalyzer` (core stats + consistency + cross-ammeter accuracy ranking).
- [x] **Gate 4**: `ResultManager`, `Visualizer`, `run_suite.py` CLI.
- [x] **Gate 5**: Error simulation + full `pytest` suite (`tests/`).
- [ ] **Gate 6**: GitHub Actions CI, sample results, final `README.md` (with bug-fix log & design decisions), git hygiene.
