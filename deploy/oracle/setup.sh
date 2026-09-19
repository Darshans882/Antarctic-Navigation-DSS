#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/antarctic-navigation-dss}"
REPO_URL="${REPO_URL:-https://github.com/hariponkarthika/Antarctic-Navigation-DSS.git}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="antarctic-dss"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root: sudo bash deploy/oracle/setup.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git python3 python3-venv python3-pip nginx nodejs npm

if [[ ! -d "${APP_DIR}/.git" ]]; then
  rm -rf "${APP_DIR}"
  git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
else
  git -C "${APP_DIR}" fetch origin "${BRANCH}"
  git -C "${APP_DIR}" checkout "${BRANCH}"
  git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
fi

python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"

cat > "/etc/${SERVICE_NAME}.env" <<EOF
APP_NAME=Antarctic Navigation DSS
HOST=127.0.0.1
PORT=8000
DATA_MODE=demo
DEMO_MODE=force
ASSISTANT_PROVIDER=none
CORS_ORIGINS=http://127.0.0.1,http://localhost
DATABASE_URL=sqlite:///${APP_DIR}/antarctic_dss.db
EOF
chmod 600 "/etc/${SERVICE_NAME}.env"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Antarctic Navigation DSS API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}/backend
EnvironmentFile=/etc/${SERVICE_NAME}.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

npm --prefix "${APP_DIR}/frontend" ci
npm --prefix "${APP_DIR}/frontend" run build
mkdir -p /var/www/antarctic-dss
rm -rf /var/www/antarctic-dss/*
cp -r "${APP_DIR}/frontend/dist/." /var/www/antarctic-dss/

cat > /etc/nginx/sites-available/antarctic-dss <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    root /var/www/antarctic-dss;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
ln -sf /etc/nginx/sites-available/antarctic-dss /etc/nginx/sites-enabled/antarctic-dss
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"
systemctl reload nginx

PUBLIC_IP="$(hostname -I | awk '{print $1}')"
echo
printf 'Deployment complete. Open: http://%s\n' "${PUBLIC_IP}"
printf 'API health: http://%s/api/health\n' "${PUBLIC_IP}"
