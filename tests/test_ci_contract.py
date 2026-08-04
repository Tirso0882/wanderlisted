"""Static contracts for hermetic, lockfile-reproducible CI coverage."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_python_ci_uses_frozen_uv_lock_for_every_code_job():
    workflow = _read(".github/workflows/ci.yml")

    assert workflow.count("uv sync --frozen --all-groups") == 4
    assert "pip install -r requirements.txt" not in workflow
    assert 'UV_VERSION: "0.11.7"' in workflow
    assert "uv run --frozen pytest tests/" in workflow


def test_ci_lints_and_formats_all_python_and_edd_sources():
    workflow = _read(".github/workflows/ci.yml")

    assert "ruff check src/ tests/ scripts/ edd/" in workflow
    assert "ruff format --check src/ tests/ scripts/ edd/" in workflow


def test_ci_runs_every_hermetic_specialist_layer1_gate_without_live_flags():
    workflow = _read(".github/workflows/ci.yml")

    assert "tests/test_edd_*.py" in workflow
    assert "python -m edd.budget.l1_run" in workflow
    assert "python -m edd.itinerary.l1_run" in workflow
    assert "python -m edd.offline_baselines verify" in workflow
    assert 'EDD_REFRESH: "0"' in workflow
    assert 'EDD_LIVE_JUDGE_APPROVED: "0"' in workflow
    assert "EDD_REFRESH=1" not in workflow


def test_frontend_ci_uses_frozen_lock_and_all_static_build_gates():
    workflow = _read(".github/workflows/ci.yml")
    package = _read("frontend/package.json")

    assert "pnpm install --frozen-lockfile" in workflow
    assert "pnpm lint" in workflow
    assert "pnpm exec tsc --noEmit" in workflow
    assert "pnpm build" in workflow
    assert '"packageManager": "pnpm@10.33.2"' in package
    assert "needs: [lint, test, eval-layer1, docs, frontend]" in workflow


def test_runtime_image_installs_only_frozen_runtime_dependencies():
    dockerfile = _read("Dockerfile")

    assert "COPY pyproject.toml uv.lock ./" in dockerfile
    assert "uv sync --frozen --no-dev --no-install-project" in dockerfile
    assert "pip install --no-cache-dir --prefix=/install" not in dockerfile
