# Oracle Cloud deployment

This deploys the full demo application on one Ubuntu Oracle Cloud VM:

- FastAPI API: systemd service on `127.0.0.1:8000`
- React/Vite frontend: Nginx on port `80`
- SQLite database: `/opt/antarctic-navigation-dss/antarctic_dss.db`
- Default mode: demo data, no external AI key required

## VM setup

Create an Oracle Cloud VM with Ubuntu 22.04/24.04. Allow ingress TCP ports `22` and `80` in the Oracle security list. Then SSH into the VM and run:

```bash
sudo apt update
sudo apt install -y git
sudo git clone https://github.com/hariponkarthika/Antarctic-Navigation-DSS.git /tmp/antarctic-dss
cd /tmp/antarctic-dss
sudo bash deploy/oracle/setup.sh
```

Open the printed public URL and check `/api/health`.

## Real data

The repository intentionally excludes the large `Real data/processed` directory. Copy that directory to `/opt/antarctic-navigation-dss/Real data/processed/` separately, then edit `/etc/antarctic-dss.env`:

```text
DATA_MODE=real
DEMO_MODE=auto
```

Restart the API:

```bash
sudo systemctl restart antarctic-dss
```

The free VM must have enough disk, RAM, and CPU for the real datasets and model artifacts. Start with demo mode before transferring them.

## Updates

```bash
sudo git -C /opt/antarctic-navigation-dss pull --ff-only origin main
sudo bash /opt/antarctic-navigation-dss/deploy/oracle/setup.sh
```
