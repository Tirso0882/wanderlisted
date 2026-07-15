"""Single source of truth for the models the EDD layers can run.

The point of this file is EASY SWAPPING. Add a model = ONE line in MODELS.
Every layer (L1 / L2 / L3) imports MODELS and refers to a model by its short key
("sol" / "terra" / "luna"), so you never re-declare a model or hand-match a long
env-var name to swap one in — you change a key, not a name.

Azure DEPLOYMENT NAMES are identifiers, not secrets, so they can live here in
code. The os.environ.get(...) wrapper is only an OPTIONAL override for when a
deployment is named differently in another environment; delete it and hardcode
the string if you prefer — nothing here needs to be in .env.

Each value is kwargs forwarded straight to run_agent() -> get_llm():
  • tier             picks the concurrency semaphore + the tier's DEFAULT effort.
  • azure_deployment pins the exact Azure deployment (overrides the tier default).

The GPT-5.6 family maps onto the project's three tiers 1:1 — Sol=reasoning,
Terra=fast, Luna=utility — so each model runs at its NATURAL tier/effort (how
you'd actually deploy it). All three are reasoning models, so none needs the
non-reasoning reasoning_effort=None workaround the deprecated gpt-4o did.
"""

from __future__ import annotations

import os

MODELS: dict[str, dict] = {
    "sol": {
        "tier": "reasoning",  # flagship -> reasoning tier (effort medium)
        "azure_deployment": os.environ.get(
            "AZURE_OPENAI_GPT56SOL_DEPLOYMENT_NAME", "gpt-5.6-sol"
        ),
    },
    "terra": {
        "tier": "fast",  # balanced worker -> fast tier (effort low)
        "azure_deployment": os.environ.get(
            "AZURE_OPENAI_GPT56TERRA_DEPLOYMENT_NAME", "gpt-5.6-terra"
        ),
    },
    "luna": {
        "tier": "utility",  # cheapest/fastest -> utility tier (effort low)
        "azure_deployment": os.environ.get(
            "AZURE_OPENAI_GPT56LUNA_DEPLOYMENT_NAME", "gpt-5.6-luna"
        ),
    },
}
