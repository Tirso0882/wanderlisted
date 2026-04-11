# ── Stage 1: Build dependencies ────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ───────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Non-root user — security best practice
RUN addgroup --system app && adduser --system --ingroup app app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ src/
COPY config/ config/
COPY custom_logging/ custom_logging/
COPY knowledge_base/ knowledge_base/
COPY pyproject.toml .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--timeout-graceful-shutdown", "30", \
     "--limit-concurrency", "100"]
