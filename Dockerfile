FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATA_MODE=real \
    DEMO_MODE=auto

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN sed '/^torch[<>=]/d' /app/backend/requirements.txt > /tmp/requirements-no-torch.txt \
    && pip install --no-cache-dir -r /tmp/requirements-no-torch.txt \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu 'torch>=2.2.0'

COPY backend /app/backend
COPY config /app/config
COPY .deploy-models/models.tar.gz /tmp/models.tar.gz
RUN tar -xzf /tmp/models.tar.gz -C /app/backend \
    && rm -f /tmp/models.tar.gz

# Reconstruct and extract only the real runtime assets. The full data archive
# remains outside the image; these four chunks keep each GitHub file under 100 MB.
COPY .deploy-assets /tmp/deploy-assets
RUN cat /tmp/deploy-assets/runtime-data.tar.gz.part-* > /tmp/runtime-data.tar.gz \
    && mkdir -p "/app/Real data/processed" \
    && tar -xzf /tmp/runtime-data.tar.gz -C "/app/Real data/processed" \
    && rm -rf /tmp/deploy-assets /tmp/runtime-data.tar.gz

COPY scripts /app/scripts
RUN mkdir -p "/app/backend/data/processed/features" \
    && if [ -f "/app/Real data/processed/iceberg/csv/iceberg_processed.csv" ]; then \
        cp "/app/Real data/processed/iceberg/csv/iceberg_processed.csv" "/app/backend/data/processed/features/feature_table.csv" 2>/dev/null || true; \
        cp "/app/Real data/processed/iceberg/csv/iceberg_processed.csv" "/app/backend/data/processed/features/iceberg_processed.csv" 2>/dev/null || true; \
       fi \
    && python3 /app/scripts/import_real_csv_to_database.py || true

WORKDIR /app/backend
EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]