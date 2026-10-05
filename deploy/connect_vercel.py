#!/usr/bin/env python3
"""Helper script to connect Vercel frontend to AWS EC2 backend.

Usage:
    python deploy/connect_vercel.py <YOUR_EC2_PUBLIC_IP_OR_HOSTNAME>

Example:
    python deploy/connect_vercel.py 54.210.120.45
"""
import sys
import json
import subprocess
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python deploy/connect_vercel.py <YOUR_EC2_PUBLIC_IP_OR_HOSTNAME>")
        print("Example: python deploy/connect_vercel.py 54.210.120.45")
        sys.exit(1)

    target = sys.argv[1].strip().replace("http://", "").replace("https://", "").rstrip("/")
    if ":" in target:
        host, port = target.split(":", 1)
    else:
        host, port = target, "8000"

    backend_url = f"http://{host}:{port}"
    repo_root = Path(__file__).resolve().parents[1]
    vercel_json_path = repo_root / "frontend" / "vercel.json"

    vercel_config = {
        "rewrites": [
            {
                "source": "/api/:path*",
                "destination": f"{backend_url}/api/:path*"
            },
            {
                "source": "/health",
                "destination": f"{backend_url}/health"
            },
            {
                "source": "/(.*)",
                "destination": "/index.html"
            }
        ]
    }

    with open(vercel_json_path, "w", encoding="utf-8") as f:
        json.dump(vercel_config, f, indent=2)

    print(f"==> Updated frontend/vercel.json to proxy /api requests to {backend_url}")
    print("==> Staging and pushing to GitHub to trigger Vercel deployment...")

    try:
        subprocess.run(["git", "add", "frontend/vercel.json"], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-m", f"chore(deploy): connect Vercel to AWS backend at {backend_url}"], cwd=repo_root, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=repo_root, check=True)
        print("\nSUCCESS! Pushed to GitHub. Vercel will now automatically deploy and connect to your EC2 backend.")
    except subprocess.CalledProcessError as e:
        print(f"\nNotice: Git push encountered an issue: {e}")
        print("Please run: git add frontend/vercel.json && git commit -m 'connect vercel' && git push origin main")

if __name__ == "__main__":
    main()
