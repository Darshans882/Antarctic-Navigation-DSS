#!/usr/bin/env bash
set -euo pipefail

pip install --upgrade pip
pip install -r backend/requirements.txt

tar -xzf .deploy-models/models.tar.gz -C backend

cat .deploy-assets/runtime-data.tar.gz.part-* > runtime-data.tar.gz
mkdir -p "Real data/processed"
tar -xzf runtime-data.tar.gz -C "Real data/processed"
rm -f runtime-data.tar.gz