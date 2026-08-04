# EDD Baselines

Named immutable EDD runs are written below this directory when a runner is
started with `EDD_BASELINE=<name>`.

`offline-current.json` points to the reviewed zero-call contract baseline for
all eight specialists. Each `offline-contract.json` records whether it executes
a deterministic pipeline (Budget/Itinerary) or only evaluator contracts (the
provider/model specialists), and always sets `model_quality_claim=false`. Verify
these source fingerprints with:

```bash
.venv/bin/python -m edd.offline_baselines verify
```

Each baseline contains content-addressed trajectory runs and append-only L1-L4
metric reports. Generated artifacts are intentionally not ignored by Git, but
they should be reviewed before committing because live tool evidence can be
large. Use `EDD_BASELINE_DIR` to store them in an external durable location.

Do not edit generated JSON files. Create a new baseline name for a new run or
experiment. See [`edd/README.md`](../README.md#verify-the-named-zero-call-contract-baseline)
for offline contracts and the named-trajectory section for live/cached artifacts.
