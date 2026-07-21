"""Regression tests for EDD entry-point runtime policy."""

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TRACING_CHECK = """
import importlib
import os
import sys

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
importlib.import_module(sys.argv[1])

from langsmith.utils import tracing_is_enabled

assert os.environ["LANGSMITH_TRACING"] == "false"
assert os.environ["LANGCHAIN_TRACING_V2"] == "false"
assert tracing_is_enabled() is False
"""


@pytest.mark.parametrize(
    "module_name",
    [
        "edd.flights.l1_run",
        "edd.hotels.l1_run",
        "edd.restaurants.l1_run",
        "edd.activities.l1_run",
        "edd.transportation.l1_run",
    ],
)
def test_layer1_runner_disables_tracing(module_name):
    result = subprocess.run(
        [sys.executable, "-c", _TRACING_CHECK, module_name],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
