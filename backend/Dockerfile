FROM python:3.11-slim

# Add curl for the HEALTHCHECK below. ca-certificates so outbound HTTPS
# (Slack webhook, ServiceNow, etc.) works on the slim base.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so changes to app code don't bust the dep cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# Persistent data volume for the SQLite database. The compose file binds a
# named volume here so the DB survives container restarts.
RUN mkdir -p /app/data

# Drop root before the application runs. Anything that mutates /app/data
# at runtime must remain writable for this user.
RUN useradd --system --uid 1001 --shell /usr/sbin/nologin marshall \
    && chown -R marshall:marshall /app
USER marshall

EXPOSE 8000

# /ready returns 503 if the DB is unreachable or PROOF_SECRET is missing;
# /health is liveness only. Use /ready here so docker / k8s pull a broken
# container out of rotation instead of restarting a healthy process.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD curl -fsS http://127.0.0.1:8000/ready || exit 1

# gunicorn with uvicorn workers.
# --workers 1 is intentional: rate-limiting and approval state are in-process today,
# so multiple workers would split that state and silently degrade enforcement.
# Move to Redis-backed state before raising worker count.
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120"]
