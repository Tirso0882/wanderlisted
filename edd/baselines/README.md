# EDD Baselines

Named immutable EDD runs are written below this directory when a runner is
started with `EDD_BASELINE=<name>`.

Each baseline contains content-addressed trajectory runs and append-only L1-L4
metric reports. Generated artifacts are intentionally not ignored by Git, but
they should be reviewed before committing because live tool evidence can be
large. Use `EDD_BASELINE_DIR` to store them in an external durable location.

Do not edit generated JSON files. Create a new baseline name for a new run or
experiment. See [`edd/README.md`](../README.md#preserve-a-named-baseline) for the
commands and artifact contract.
