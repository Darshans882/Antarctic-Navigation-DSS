# AWS Deployment & Troubleshooting Guide for Antarctic Navigation DSS

This guide resolves backend hosting issues on AWS (EC2 / ECS / Lightsail) and fixes connectivity between your hosted frontend (Vercel) and the AWS backend.

---

## The 4 Common Reasons AWS Hosted Backends Fail

1. **AWS EC2 Security Group blocks Port 8000**:
   - AWS EC2 firewalls block all inbound traffic except SSH (port 22) by default.
   - **Fix**: Open Port 8000 in your EC2 Security Group inbound rules.

2. **Mixed Content Error (HTTPS Frontend calling HTTP Backend)**:
   - If your frontend is on Vercel (`https://...`), web browsers block all direct API calls to plain HTTP (`http://<EC2-IP>:8000`) for security.
   - **Fix**: Use the Vercel Server-Side Rewrite Proxy (Option 1 below, no SSL needed on AWS!) or Cloudflare Tunnel (Option 2 below).

3. **CORS Restrictions**:
   - The backend was previously hardcoded to only allow `https://antarctic-navigation-dss.vercel.app`.
   - **Fixed in code**: The backend now supports all `*.vercel.app` domains, `https://antarctic-navigation-frontend.vercel.app`, and custom origins.

4. **Missing Runtime Models, Data & Database on AWS**:
   - The git repository does not store unpacked models, databases, or large NetCDF data (they are stored compressed in `.deploy-assets/` and `.deploy-models/`).
   - If you only cloned git and started uvicorn without extracting them, the backend lacks data and routes/iceberg queries fail.
   - **Fixed**: We provided `deploy/setup_aws_backend.sh` which extracts everything, seeds the SQLite database, and creates a 24/7 systemd service.

---

## Step 1: Run the Automated Backend Setup on AWS EC2

SSH into your AWS EC2 instance and run:

```bash
# 1. Navigate to your project directory
cd ~/Antarctic-Navigation-DSS  # (or wherever your project was cloned)

# 2. Pull the latest fixes
git pull origin main

# 3. Make the setup script executable and run it
chmod +x deploy/setup_aws_backend.sh
./deploy/setup_aws_backend.sh
```

### What this script does automatically:
- Creates a **4GB swap space** so PyTorch and machine-learning dependencies do not get killed by Linux OOM on `t2.micro` / `t3.micro` instances.
- Sets up `.venv` with CPU-optimized PyTorch and all dependencies.
- Extracts models from `.deploy-models/` and datasets from `.deploy-assets/`.
- Populates the database (`antarctic_dss.db`) with real iceberg and vessel data.
- Registers and starts a `systemd` daemon (`antarctic-dss`) running on `0.0.0.0:8000` that automatically restarts if it crashes or the server reboots.

### Check service status anytime:
```bash
sudo systemctl status antarctic-dss
# Or view live logs:
sudo journalctl -u antarctic-dss -f
```

---

## Step 2: Open Port 8000 in AWS EC2 Security Group

1. Open the **AWS Management Console** -> **EC2** -> **Instances**.
2. Click your instance -> click the **Security** tab below.
3. Click the **Security groups** link (e.g. `launch-wizard-1` or `default`).
4. Click **Edit inbound rules**.
5. Click **Add rule**:
   - **Type**: Custom TCP
   - **Port range**: `8000`
   - **Source**: `0.0.0.0/0` (Anywhere-IPv4)
6. Click **Save rules**.

Test that it is reachable from your local browser or terminal:
```bash
curl http://<YOUR_EC2_PUBLIC_IP>:8000/api/health
```
You should receive `{"status":"ok", ...}`.

---

## Step 3: Connect Vercel Frontend to AWS Backend

Because Vercel runs on **HTTPS**, choose either **Method A** (easiest, no SSL required on EC2) or **Method B**:

### Method A: Vercel Reverse Proxy (Recommended — No SSL Setup Required on AWS)

Vercel can act as a secure server-side reverse proxy. The browser calls `https://your-app.vercel.app/api/...` (HTTPS), and Vercel forwards it to `http://<EC2-IP>:8000/api/...`. No Mixed Content or CORS errors!

1. Edit [frontend/vercel.json](file:///c:/my%20project/SIH%20HACK%20FINAL%20PROJ/SIH%20HACK/frontend/vercel.json):
```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "http://<YOUR_EC2_PUBLIC_IP>:8000/api/:path*"
    },
    {
      "source": "/health",
      "destination": "http://<YOUR_EC2_PUBLIC_IP>:8000/api/health"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```
2. Remove or leave `VITE_API_BASE_URL` empty in Vercel environment variables (so the frontend uses same-origin `/api`).
3. Deploy frontend to Vercel:
```bash
cd frontend
npx vercel --prod
```

---

### Method B: Free Instant HTTPS with Cloudflare Tunnel on EC2

If you prefer direct frontend-to-backend calls with public HTTPS:

1. On your AWS EC2 instance, install `cloudflared`:
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```
2. Start a tunnel:
```bash
cloudflared tunnel --url http://localhost:8000
```
3. Cloudflare gives you a free HTTPS URL: `https://xxxx.trycloudflare.com`.
4. Update your Vercel environment variable `VITE_API_BASE_URL` to `https://xxxx.trycloudflare.com` and redeploy!
