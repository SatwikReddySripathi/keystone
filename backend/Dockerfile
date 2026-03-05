FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATABASE_PATH=/app/data/keystone.db
ENV PROOF_SECRET=keystone-dev-secret-change-in-production
ENV DEFAULT_ORG_ID=org_demo
ENV DEFAULT_API_KEY=ks_test_demo_key_001

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]