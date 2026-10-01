#!/usr/bin/env bash
set -euo pipefail

pip install --upgrade pip
pip install -r backend/requirements.txt

tar -xzf .deploy-models/models.tar.gz -C backend

cat .deploy-assets/runtime-data.tar.gz.part-* > runtime-data.tar.gz
mkdir -p "Real data/processed"
tar -xzf runtime-data.tar.gz -C "Real data/processed"
rm -f runtime-data.tar.gz

mkdir -p "backend/data/processed/features"
if [ -f "Real data/processed/iceberg/csv/iceberg_processed.csv" ]; then
  cp -n "Real data/processed/iceberg/csv/iceberg_processed.csv" "backend/data/processed/features/feature_table.csv" 2>/dev/null || true
  cp -n "Real data/processed/iceberg/csv/iceberg_processed.csv" "backend/data/processed/features/iceberg_processed.csv" 2>/dev/null || true
fi