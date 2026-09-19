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

# Package the real runtime assets selected by services.data_paths and the
# routing land mask. The remaining multi-gigabyte data archive stays external.
COPY ["Real data/processed/sea_ice/csv/sea_ice_latest_part_202312.csv", "/app/Real data/processed/sea_ice/csv/sea_ice_latest_part_202312.csv"]
COPY ["Real data/processed/ocean/csv/ocean_part_202201.csv", "/app/Real data/processed/ocean/csv/ocean_part_202201.csv"]
COPY ["Real data/processed/weather/csv/weather_part_202201.csv", "/app/Real data/processed/weather/csv/weather_part_202201.csv"]
COPY ["Real data/processed/iceberg/csv/iceberg_processed.csv", "/app/Real data/processed/iceberg/csv/iceberg_processed.csv"]
COPY ["Real data/processed/bathymetry/land_ocean_mask.json", "/app/Real data/processed/bathymetry/land_ocean_mask.json"]
COPY ["Real data/processed/vessel/csv/vessel_processed.csv", "/app/Real data/processed/vessel/csv/vessel_processed.csv"]

WORKDIR /app/backend
EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
