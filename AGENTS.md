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

## 2. Core Architecture (OOP & Scalable)
- **Scalable Ammeter Adapters (`src/ammeters/`)**:
  - `BaseAmmeterAdapter` (ABC) defines the common interface for connecting, querying, and validating readings.
  - Dedicated subclasses (`GreenleeAdapter`, `EntesAdapter`, `CircutorAdapter`) encapsulate ammeter-specific protocol/metadata.
  - Registry/Factory (`AmmeterFactory`) enables adding 4th/5th ammeter types without modifying core framework or analysis code.
- **Shared Analytics (`src/analysis/`)**:
  - `StatisticalAnalyzer` computes `mean`, `median`, `std_dev`, `min`, `max`, `CV`, `IQR`, `CI95`, and cross-ammeter accuracy/precision ranking once for all ammeter types (zero duplication).
- **Sampling (`src/testing/sampler.py`)**:
  - Supports any 2-of-3 of (`measurements_count`, `total_duration_seconds`, `sampling_frequency_hz`) and validates consistency if all 3 are provided.
  - Uses `time.perf_counter()` drift-compensated scheduling.
  - Supports configurable error simulation for negative QA tests.
- **Result Management (`src/storage/result_manager.py`)**:
  - Unique `run_id`, JSON persistence with metadata + raw samples + stats, historical retrieval & comparison.
- **Visualization (`src/visualization/visualizer.py`)**:
  - Headless `matplotlib` (`Agg`) PNG reports under `results/plots/`.
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
- [ ] **Gate 2**: OOP Ammeter Adapters (`src/ammeters/`), `config.py` validation + 2-of-3 sampling, `sampler.py`, `AmmeterTestFramework`.
- [ ] **Gate 3**: `StatisticalAnalyzer` (core stats + consistency + cross-ammeter accuracy ranking).
- [ ] **Gate 4**: `ResultManager`, `Visualizer`, `run_suite.py` CLI.
- [ ] **Gate 5**: Error simulation + full `pytest` suite (`tests/`).
- [ ] **Gate 6**: GitHub Actions CI, sample results, final `README.md` (with bug-fix log & design decisions), git hygiene.
