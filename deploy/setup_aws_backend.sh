#!/usr/bin/env bash
# =============================================================================
# Automated Setup & Deployment Script for AWS EC2 (Ubuntu / Debian / Amazon Linux)
# Antarctic Navigation Decision Support System (FastAPI Backend)
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=================================================================="
echo "==> Setting up Antarctic Navigation DSS Backend on AWS..."
echo "==> Working directory: $REPO_DIR"
echo "=================================================================="

# 1. Setup 4GB Swap Space (Essential for EC2 t2/t3.micro instances)
if [ ! -f /swapfile ] && [ "$(id -u)" -eq 0 -o "$(command -v sudo)" ]; then
    echo "==> Configuring 4GB swap to prevent Out-Of-Memory (OOM) during ML inference..."
    sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile || true
    if ! grep -q "/swapfile" /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
    echo "==> Swap space configured successfully."
fi

# 2. Install System Packages if on Debian/Ubuntu
if command -v apt-get >/dev/null 2>&1; then
    echo "==> Updating apt packages..."
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv build-essential curl git
fi

# 3. Create and activate Python Virtual Environment
echo "==> Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 4. Install Dependencies (CPU-optimized PyTorch first)
echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu 'torch>=2.2.0'
pip install --no-cache-dir -r backend/requirements.txt

# 5. Extract Trained Models
echo "==> Extracting ML models into backend..."
if [ -f ".deploy-models/models.tar.gz" ]; then
    tar -xzf .deploy-models/models.tar.gz -C backend
    echo "==> Models extracted successfully."
fi

# 6. Extract Processed Real Datasets
echo "==> Reconstructing and extracting real processed datasets..."
if [ -d ".deploy-assets" ] && compgen -G ".deploy-assets/runtime-data.tar.gz.part-*" > /dev/null; then
    cat .deploy-assets/runtime-data.tar.gz.part-* > /tmp/runtime-data.tar.gz
    mkdir -p "Real data/processed"
    tar -xzf /tmp/runtime-data.tar.gz -C "Real data/processed"
    rm -f /tmp/runtime-data.tar.gz
    echo "==> Real datasets extracted successfully."
fi

# 7. Copy Iceberg Feature Tables
echo "==> Setting up feature tables..."
mkdir -p "backend/data/processed/features"
if [ -f "Real data/processed/iceberg/csv/iceberg_processed.csv" ]; then
    cp -n "Real data/processed/iceberg/csv/iceberg_processed.csv" "backend/data/processed/features/feature_table.csv" 2>/dev/null || true
    cp -n "Real data/processed/iceberg/csv/iceberg_processed.csv" "backend/data/processed/features/iceberg_processed.csv" 2>/dev/null || true
fi

# 8. Initialize and Seed the SQLite Database
echo "==> Initializing and populating database with real observations..."
python3 scripts/import_real_csv_to_database.py || echo "Warning: Database seeding script had warnings; continuing."

# 9. Configure systemd Service for 24/7 Background Running
CURRENT_USER="$(whoami)"
SERVICE_FILE="/etc/systemd/system/antarctic-dss.service"

if command -v sudo >/dev/null 2>&1; then
    echo "==> Registering systemd service at $SERVICE_FILE..."
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Antarctic Navigation Decision Support System (FastAPI)
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$REPO_DIR/backend
Environment="PATH=$REPO_DIR/.venv/bin:/usr/local/bin:/usr/bin"
Environment="HOST=0.0.0.0"
Environment="PORT=8000"
Environment="DATA_MODE=real"
Environment="DEMO_MODE=off"
ExecStart=$REPO_DIR/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable antarctic-dss
    sudo systemctl restart antarctic-dss
    echo "==> systemd service started and enabled on boot."
fi

# 10. Health Check
echo "==> Verifying service health..."
sleep 3
if curl -s -f http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "=================================================================="
    echo "SUCCESS: Antarctic DSS Backend is RUNNING on http://0.0.0.0:8000"
    echo "Health check endpoint: http://127.0.0.1:8000/api/health"
    echo "Root check endpoint:   http://127.0.0.1:8000/"
    echo "Interactive API docs:  http://127.0.0.1:8000/docs"
    echo "=================================================================="
    echo "AWS EC2 CHECKLIST:"
    echo "1. Go to AWS EC2 Console -> Security Groups."
    echo "2. Edit Inbound Rules -> Add rule: Custom TCP, Port 8000, Source 0.0.0.0/0 (Anywhere-IPv4)."
    echo "3. If connecting directly from Vercel (HTTPS), configure Vercel rewrite or use Cloudflare Tunnel."
    echo "=================================================================="
else
    echo "==> Service starting up or needs inspection. Check logs with:"
    echo "    sudo journalctl -u antarctic-dss -n 50 --no-pager"
fi
