# Deployment Guide

Deployment notes for the Debt Management BI / Receivables Analytics Platform.

This document describes the current demo deployment and the planned secured work/production deployment.

---

# Current deployment status

## Demo environment

Public demo URL:

```text
https://demo.maximvenevtsev.com
```

Purpose:

- portfolio showcase
- recruiter demo
- controlled business demonstration
- architecture validation

Data:

- anonymized / generated demo dataset
- no real client-sensitive data
- safe for public access

---

# Deployment topology

```text
Internet
    ↓
Cloudflare DNS
    ↓
Nginx reverse proxy
    ↓
NiceGUI application
    ↓
PostgreSQL
```

---

# Server

## VPS

Provider:

```text
FirstVDS
```

Server: 
```text
Ubuntu 24.04 VPS
```

Public IP: 
```text
83.220.168.3
```

Domain: 

```text
maximvenevtsev.com
```

Current demo subdomain: 

```text
demo.maximvenevtsev.com
```


---

# DNS

DNS provider: Cloudflare

Current DNS record:

```text
Type: A
Name: demo
Content: 83.220.168.3
Proxy status: DNS only
TTL: Auto
```

Result:

demo.maximvenevtsev.com -> 83.220.168.3

---

# Server stack

Installed components:

- Ubuntu 24.04
- Python 3
- PostgreSQL
- Nginx
- Git
- UFW firewall
- Certbot / Let's Encrypt
- systemd service

---

# Linux users

root

Used only for initial setup and administrative tasks.

deploy

Main application deployment user.

Home directory:

```bash
/home/deploy
```

Application directory:

```bash
/home/deploy/receivables-analytics-platform
```

SSH access:

```bash
ssh deploy@83.220.168.3
```

# Firewall

UFW is enabled.

Allowed services:

- OpenSSH
- Nginx Full

Expected ports:

```text
22/tcp
80/tcp
443/tcp
```

---

# PostgreSQL

## Demo database

Database:

receivables_demo

User:

receivables_user

Password:

stored in .env

Important:

- `.env` must never be committed
- database password should not be stored in documentation
- demo database contains anonymized/generated data only

---

# Environment file

Current application .env location on VPS:

/home/deploy/receivables-analytics-platform/.env

Expected variables:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=receivables_demo
DB_USER=receivables_user
DB_PASSWORD=<stored on server only>

APP_ENV=demo
```

---

# Demo application service

The demo application is managed by systemd.

Service name:

receivables-demo

Service file:

/etc/systemd/system/receivables-demo.service

Current service configuration:

```ini
[Unit]
Description=Receivables Analytics Demo
After=network.target postgresql.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/receivables-analytics-platform
Environment="PATH=/home/deploy/receivables-analytics-platform/.venv/bin"
ExecStart=/home/deploy/receivables-analytics-platform/.venv/bin/python -m src.app.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Useful commands:

```bash
sudo systemctl status receivables-demo
sudo systemctl restart receivables-demo
sudo systemctl stop receivables-demo
sudo systemctl start receivables-demo
```

View logs:

```bash
journalctl -u receivables-demo -f
```

---

# Nginx

Demo Nginx config:

/etc/nginx/sites-available/receivables-demo

Enabled via:

/etc/nginx/sites-enabled/receivables-demo

Current reverse proxy target:

```text
http://127.0.0.1:8080
```

Typical config:

```nginx
server {
    listen 80;
    server_name demo.maximvenevtsev.com;

    location / {
        proxy_pass http://127.0.0.1:8080;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Check Nginx config:

sudo nginx -t

Reload Nginx:

sudo systemctl reload nginx

---

# HTTPS

HTTPS is enabled with Let's Encrypt / Certbot.

Certificate domain:

demo.maximvenevtsev.com

Certificate files:

/etc/letsencrypt/live/demo.maximvenevtsev.com/fullchain.pem
/etc/letsencrypt/live/demo.maximvenevtsev.com/privkey.pem

Certbot renewal is scheduled automatically.

Check certificates:

sudo certbot certificates

Renewal dry run:

sudo certbot renew --dry-run

---

# Deployment workflow

Local machine

Development and commits should be done locally.

Typical workflow:

```bash
git status
git add <files>
git commit -m "Commit message"
git push
```

## VPS

The VPS acts as deployment target.

Typical update workflow:

```bash
ssh deploy@83.220.168.3

cd ~/receivables-analytics-platform

git pull

sudo systemctl restart receivables-demo
```

Do not normally commit from the VPS.

---

# Demo dataset

Demo dataset files:

```text
data/demo/receivables_snapshot_demo.csv
data/demo/receivables_snapshot_demo.xlsx
```

Generate sanitized demo dataset:

```text
python tools/export_demo_dataset.py
```

The demo dataset is generated from normalized PostgreSQL views and should not contain real sensitive data.

---

# Real work / production environment plan

The next planned deployment environment is a secured work version with real operational data.

Planned URL:

https://work.maximvenevtsev.com

Planned characteristics:

- separate application directory
- separate PostgreSQL database
- separate .env
- password-protected access
- real ERP exports ingestion
- daily snapshot loading
- scheduled ETL
- backup strategy
- production logging

# Planned work environment structure

Recommended directory:

/home/deploy/receivables-work

Recommended database:

receivables_work

Recommended systemd service:

receivables-work

Recommended subdomain:

work.maximvenevtsev.com

Recommended app port:

8081

Expected separation:

demo.maximvenevtsev.com
    -> receivables-demo
    -> receivables_demo
    -> port 8080

work.maximvenevtsev.com
    -> receivables-work
    -> receivables_work
    -> port 8081

# Work environment access protection

Initial recommended protection:

Nginx Basic Auth

Reason:

fast to implement
suitable for controlled MVP testing
does not require application-level auth yet
easy to share with selected users

Later production versions may include:

application-level authentication
user roles
branch-level access
audit logs

# Sensitive data rules

Real ERP exports must not be committed to GitHub.

Recommended ignored paths:

data/raw/
data/raw_real/
data/work/
data/staging/
data/logs/

Rules:

- no real client names in public screenshots
- no real ERP files in GitHub
- no .env in GitHub
- no passwords in documentation
- production/work data must be separated from demo data

---

# Backup strategy

Not fully implemented yet.

Recommended next steps:

daily PostgreSQL dump
backup retention policy
backup location outside application directory
restore test procedure
optional VPS-level backup after production validation

Example future backup command:

```bash
pg_dump -U receivables_user -d receivables_work > backups/receivables_work_YYYY_MM_DD.sql
```

---

# Monitoring / logs

Current demo:

systemd restart policy enabled
logs available via journalctl

Useful commands:

```bash
journalctl -u receivables-demo -f
sudo systemctl status receivables-demo
sudo nginx -t
sudo systemctl status nginx
sudo systemctl status postgresql
```

Planned production improvements:

- structured application logging
- ETL run logs
- ingestion status table
- failed-load alerts
- backup logs

---

# Production rollout checklist

- [ ] Validate real ERP exports
- [ ] Create production PostgreSQL database
- [ ] Configure protected subdomain
- [ ] Enable Basic Auth
- [ ] Configure backups
- [ ] Configure ETL schedule
- [ ] Validate HTTPS
- [ ] Run first production load

# Immediate next steps

1. Validate real ERP reports locally.
2. Adapt ingestion pipeline for full branch structure.
3. Load real snapshots into a separate work database.
4. Create work.maximvenevtsev.com DNS record.
5. Deploy work environment in parallel with demo.
6. Protect work environment with Nginx Basic Auth.
7. Add daily ETL process.
8. Implement backup strategy.