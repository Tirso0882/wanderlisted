# ── Stage 1: Build dependencies ────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir --timeout=120 --retries=3 uv==0.11.7 \
    && uv sync --frozen --no-dev --no-install-project

# ── Stage 2: Runtime ───────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# CA certificates (needed for LangSmith and other HTTPS clients)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — security best practice
RUN addgroup --system app && adduser --system --ingroup app app

# Copy the lockfile-resolved runtime environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ src/
COPY config/ config/
COPY custom_logging/ custom_logging/
COPY pyproject.toml .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Create writable logs dir before dropping privileges
RUN mkdir -p logs && chown app:app logs

USER app

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--timeout-graceful-shutdown", "30", \
     "--limit-concurrency", "100"]
