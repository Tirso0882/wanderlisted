"""EDD — Hotels agent evaluation suite (all layers).

One package per agent. The l{N}_ filename prefix is the evaluation layer:
    Layer 1 (code-based)   : l1_dataset.py, l1_observe.py, l1_evaluate.py, l1_run.py
    Layer 2 (LLM-as-judge) : l2_judge.py, l2_judge_run.py
    Layer 2/4 (judge data) : l2_judge_cases.py   (labeled trajectories)
    Layer 3 (experiments)  : l3_judge_ab.py      (judge effort A/B)

The shared "run + capture" machinery lives one level up in edd/harness.py.
"""
