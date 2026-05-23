FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN mkdir -p /app/data

EXPOSE 8000

# gunicorn with uvicorn workers.
# --workers 1 is intentional: rate-limiting and approval state are in-process today,
# so multiple workers would split that state and silently degrade enforcement.
# Move to Redis-backed state before raising worker count.
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120"]
