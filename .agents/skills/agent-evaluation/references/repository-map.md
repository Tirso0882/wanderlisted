# Evaluation repository map

- `edd/harness.py`: captured component trajectory contract.
- `edd/<component>/l1_*`: deterministic cases/evaluation and observation runners.
- `edd/<component>/l2_*`: pointwise semantic judges.
- `edd/<component>/l3_*`: pairwise comparison.
- `edd/<component>/l4_calibrate.py`: human-label calibration.
- `edd/baseline_config.py` and `edd/baseline_store.py`: baseline registration/storage.
- `src/evaluation/`: shared/end-to-end datasets and evaluators.
- `scripts/eval_agents.py`: LangSmith-backed experiment path; external mutation and model calls require approval.
- `tests/test_edd_*.py`: hermetic EDD contract tests.
- `tests/test_edd_runtime.py` and `tests/test_edd_baselines.py`: package and baseline registration.

Read the current package before claiming layer completeness. Some run scripts can capture live data on a cache miss even without `EDD_REFRESH=1`.
