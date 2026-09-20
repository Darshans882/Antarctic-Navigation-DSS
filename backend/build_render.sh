#!/bin/bash
set -e

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Extracting models..."
tar -xzf ../.deploy-models/models.tar.gz -C .

echo "Extracting runtime data..."
cat ../.deploy-assets/runtime-data.tar.gz.part-* > ../runtime-data.tar.gz
mkdir -p "../Real data/processed"
tar -xzf ../runtime-data.tar.gz -C "../Real data/processed"
rm ../runtime-data.tar.gz

echo "Build complete!"
