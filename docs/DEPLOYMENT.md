# Deployment Guide

Deployment notes for the Debt Management BI / Receivables Analytics Platform.

This document describes the current public demo deployment and the current private work deployment.

---

# Current deployment status

## Demo environment

Public demo URL:

```text
https://demo.maximvenevtsev.com
```

Purpose:

- portfolio showcase;
- recruiter demo;
- controlled business demonstration;
- architecture validation.

Data:

- anonymized / generated demo dataset;
- no real client-sensitive data;
- safe for public access.

## Private work environment

Private work URL:

```text
https://work.maximvenevtsev.com
```

Status:

- Production MVP Deployment v1 is live;
- release tag: `work-deploy-v1`;
- protected by Nginx Basic Auth;
- uses real operational data;
- contains real receivables snapshots;
- dashboard displays the latest snapshot date as `Данные обновлены: dd.mm.yyyy`;
- browser title is `Кофточки+`;
- favicon is enabled.

Important:

- do not document Basic Auth passwords;
- do not document database passwords;
- do not include real client names in documentation or screenshots;
- `.env` files must never be committed.

---

# Environment separation

```text
demo.maximvenevtsev.com
    -> systemd service: receivables-demo
    -> database: receivables_demo
    -> app port: 8080

work.maximvenevtsev.com
    -> systemd service: receivables-work
    -> database: receivables_work
    -> app port: 8081
```

The public demo and private work deployments must remain isolated:

- separate application directories;
- separate `.env` files;
- separate PostgreSQL databases;
- separate systemd services;
- separate Nginx site configs;
- separate data directories;
- separate release/update workflow.

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

Subdomains:

```text
demo.maximvenevtsev.com
work.maximvenevtsev.com
```

---

# DNS

DNS provider:

```text
Cloudflare
```

DNS mode:

```text
DNS only
```

Current records:

```text
Type: A
Name: demo
Content: 83.220.168.3
Proxy status: DNS only
TTL: Auto

Type: A
Name: work
Content: 83.220.168.3
Proxy status: DNS only
TTL: Auto
```

Result:

```text
demo.maximvenevtsev.com -> 83.220.168.3
work.maximvenevtsev.com -> 83.220.168.3
```

---

# Server stack

Installed components:

- Ubuntu 24.04;
- Python 3;
- PostgreSQL;
- Nginx;
- Git;
- UFW firewall;
- Certbot / Let's Encrypt;
- systemd service management.

---

# Linux users

## root

Used only for initial setup and administrative tasks.

## deploy

Main application deployment user.

Home directory:

```bash
/home/deploy
```

Demo application directory:

```bash
/home/deploy/receivables-analytics-platform
```

Work application directory:

```bash
/home/deploy/receivables-work
```

SSH access:

```bash
ssh deploy@83.220.168.3
```

---

# Firewall

UFW is enabled.

Allowed services:

- OpenSSH;
- Nginx Full.

Expected ports:

```text
22/tcp
80/tcp
443/tcp
```

Application ports `8080` and `8081` should remain bound for local reverse proxy access only.

---

# PostgreSQL

## Demo database

Database:

```text
receivables_demo
```

User:

```text
receivables_user
```

Password:

```text
stored in server .env only
```

Important:

- demo database contains anonymized/generated data only;
- database password must not be stored in documentation.

## Work database

Database:

```text
receivables_work
```

User:

```text
receivables_user
```

Password:

```text
stored in /home/deploy/receivables-work/.env only
```

Important:

- work database contains real operational snapshots;
- database password must not be stored in documentation;
- real client names must not be stored in documentation.

---

# Environment files

## Demo .env

Location:

```bash
/home/deploy/receivables-analytics-platform/.env
```

Expected variables:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=receivables_demo
DB_USER=receivables_user
DB_PASSWORD=<stored on server only>

APP_ENV=demo
```

## Work .env

Location:

```bash
/home/deploy/receivables-work/.env
```

Expected variables:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=receivables_work
DB_USER=receivables_user
DB_PASSWORD=<stored on server only>

APP_ENV=work

RAW_DIR=/home/deploy/receivables-work-data/raw
ARCHIVE_DIR=/home/deploy/receivables-work-data/archive
FAILED_DIR=/home/deploy/receivables-work-data/failed

YAHOO_IMAP_HOST=imap.mail.yahoo.com
YAHOO_IMAP_PORT=993
YAHOO_IMAP_USER=<mailbox stored on server only>
YAHOO_IMAP_PASSWORD=<Yahoo App Password stored on server only>
MAIL_SOURCE_FOLDER=ARS Reports
MAIL_PROCESSED_FOLDER=ARS Processed
MAIL_FAILED_FOLDER=ARS Failed
MAIL_ALLOWED_SENDERS=tatiana.mironova@paintgroup.ru
MAIL_ALLOWED_EXTENSIONS=.txt,.xls,.xlsx
MAIL_INBOX_DIR=/home/deploy/receivables-work-data/mail_inbox
MAIL_MANIFEST_PATH=/home/deploy/receivables-work-data/mail_manifest.json
MAIL_LOG_PATH=/home/deploy/receivables-work-data/logs/mail_gateway.jsonl

AUTOMATION_RAW_DIR=/home/deploy/receivables-work-data/raw
AUTOMATION_LOG_PATH=/home/deploy/receivables-work-data/logs/orchestrator.jsonl
```

Yahoo authentication requires an App Password. Do not use or document the real mailbox password.

---

# Application services

## Demo service

The demo application is managed by systemd.

Service name:

```text
receivables-demo
```

Service file:

```text
/etc/systemd/system/receivables-demo.service
```

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
sudo systemctl status receivables-demo --no-pager
sudo systemctl restart receivables-demo
sudo systemctl stop receivables-demo
sudo systemctl start receivables-demo
journalctl -u receivables-demo -f
```

## Work service

The private work application is managed by systemd.

Service name:

```text
receivables-work
```

Service file:

```text
/etc/systemd/system/receivables-work.service
```

Application directory:

```bash
/home/deploy/receivables-work
```

Useful commands:

```bash
sudo systemctl status receivables-work --no-pager
sudo systemctl restart receivables-work
journalctl -u receivables-work -f
```

---

# Nginx

## Demo Nginx config

Config:

```text
/etc/nginx/sites-available/receivables-demo
```

Enabled via:

```text
/etc/nginx/sites-enabled/receivables-demo
```

Reverse proxy target:

```text
http://127.0.0.1:8080
```

## Work Nginx config

Config:

```text
/etc/nginx/sites-available/receivables-work
```

Enabled via:

```text
/etc/nginx/sites-enabled/receivables-work
```

Reverse proxy target:

```text
http://127.0.0.1:8081
```

Basic Auth file:

```text
/etc/nginx/.htpasswd-work
```

Basic Auth user:

```text
User
```

Do not document the Basic Auth password.

Check and reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Typical reverse proxy block:

```nginx
location / {
    proxy_pass http://127.0.0.1:8081;

    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

---

# HTTPS

HTTPS is enabled with Let's Encrypt / Certbot.

Certificate domains:

```text
demo.maximvenevtsev.com
work.maximvenevtsev.com
```

Work certificate files:

```text
/etc/letsencrypt/live/work.maximvenevtsev.com/fullchain.pem
/etc/letsencrypt/live/work.maximvenevtsev.com/privkey.pem
```

Certbot renewal is scheduled automatically.

Verification commands:

```bash
sudo certbot certificates
sudo certbot renew --dry-run
```

---

# Git remotes and release

## Demo repository

The existing public demo deployment remains on:

```text
https://demo.maximvenevtsev.com
```

## Private work repository

Remote:

```text
work -> https://github.com/Maxim-Venevtsev/receivables-work-platform.git
```

Release tag:

```text
work-deploy-v1
```

Do not store deployment tokens or credentials in documentation.

---

# Deployment and update workflows

## Local development workflow

Development and commits should normally be done locally.

Typical workflow:

```bash
git status
git add <files>
git commit -m "Commit message"
git push
```

## Demo VPS update workflow

```bash
ssh deploy@83.220.168.3

cd /home/deploy/receivables-analytics-platform
git pull
sudo systemctl restart receivables-demo
```

## Private work VPS update workflow

```bash
ssh deploy@83.220.168.3

cd /home/deploy/receivables-work
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart receivables-work
```

Do not normally commit from the VPS.

---

# Work data directories

Real work data directories:

```text
/home/deploy/receivables-work-data/raw
/home/deploy/receivables-work-data/archive
/home/deploy/receivables-work-data/failed
/home/deploy/receivables-work-data/mail_inbox
/home/deploy/receivables-work-data/logs
```

Rules:

- real ERP exports must not be committed to GitHub;
- raw files should be moved to `archive` after successful ingestion;
- failed files should be isolated in `failed`;
- Mail Gateway writes validated attachments into `mail_inbox`;
- Orchestrator hands eligible `mail_inbox` files into `raw`;
- do not include real client names in documentation.

Recommended ignored paths:

```text
data/raw/
data/raw_real/
data/work/
data/staging/
data/logs/
```

---

# Automation Layer deployment

## Processing pipeline

```text
Yahoo Mail
    ↓
ARS Reports
    ↓
Mail Gateway
    ↓
mail_inbox
    ↓
Orchestrator
    ↓
raw_work
    ↓
Existing ingestion pipeline
    ↓
archive_work / failed_work
    ↓
PostgreSQL
    ↓
Dashboard
```

Responsibilities:

- Yahoo Mail stores incoming ARS report emails.
- `ARS Reports` is the mailbox folder scanned by Mail Gateway.
- Mail Gateway authenticates via Yahoo IMAP App Password, validates sender and attachment extension, computes SHA256, skips duplicates using its manifest, writes accepted files into `MAIL_INBOX_DIR`, logs JSONL events and routes messages to processed or failed folders.
- `mail_inbox` is the pre-ingestion staging directory and supports backlog processing after restarts.
- Orchestrator optionally runs Mail Gateway, scans `MAIL_INBOX_DIR`, safely hands eligible files into `AUTOMATION_RAW_DIR`, scans raw and runs existing ingestion only when eligible raw files exist.
- `raw_work` / `RAW_DIR` is the source of truth for ingestion execution.
- Existing ingestion parses, loads, archives and fails files according to its current business logic.
- PostgreSQL and the dashboard are updated only through the existing ingestion and SQL view layers.

Mail Gateway and Orchestrator do not modify parsing, mapping, rating or SQL business logic.

## Recommended deployment order

1. Deploy code.
2. Create runtime directories.
3. Configure `.env`.
4. Dry-run Mail Gateway.
5. Dry-run Orchestrator.
6. Run one real execution.
7. Add cron or systemd timer scheduling.

Create runtime directories:

```bash
mkdir -p /home/deploy/receivables-work-data/raw
mkdir -p /home/deploy/receivables-work-data/archive
mkdir -p /home/deploy/receivables-work-data/failed
mkdir -p /home/deploy/receivables-work-data/mail_inbox
mkdir -p /home/deploy/receivables-work-data/logs
```

Dry-run Mail Gateway:

```bash
cd /home/deploy/receivables-work
source .venv/bin/activate
python -m src.automation.mail_gateway.cli --dry-run --limit 5
```

Dry-run Orchestrator:

```bash
cd /home/deploy/receivables-work
source .venv/bin/activate
python -m src.automation.orchestrator.cli --dry-run --limit 5
```

Handoff-only test without ingestion:

```bash
python -m src.automation.orchestrator.cli --skip-mail --skip-ingestion --limit 1
```

Real one-message execution:

```bash
python -m src.automation.orchestrator.cli --limit 1
```

Future cron example:

```cron
15 7 * * * cd /home/deploy/receivables-work && . .venv/bin/activate && python -m src.automation.orchestrator.cli >> /home/deploy/receivables-work-data/logs/orchestrator.cron.log 2>&1
```

Review cron timing with the business report delivery schedule before enabling.

---

# Demo dataset

Demo dataset files:

```text
data/demo/receivables_snapshot_demo.csv
data/demo/receivables_snapshot_demo.xlsx
```

Generate sanitized demo dataset:

```bash
python tools/export_demo_dataset.py
```

The demo dataset is generated from normalized PostgreSQL views and should not contain real sensitive data.

---

# Initial work database migration

Initial source database on local machine:

```text
debt_management_work
```

Server target database:

```text
receivables_work
```

Migration note:

- local PostgreSQL 18 custom-format dumps were not compatible with server PostgreSQL 16 `pg_restore`;
- plain SQL dump/restore was used for the initial migration;
- when PostgreSQL major versions differ, prefer plain SQL dumps for compatibility.

Recommended version-safe pattern:

```bash
pg_dump -Fp -d debt_management_work > receivables_work.sql
psql -d receivables_work -f receivables_work.sql
```

Adjust host, user and file paths as needed. Do not include passwords in commands or documentation.

---

# Post-deploy configuration backups

Post-deploy backups were created for the work deployment:

```text
/home/deploy/backups/post_deploy/receivables-work
/home/deploy/backups/post_deploy/receivables-work.service
```

These backups are for deployment configuration recovery and do not replace PostgreSQL data backups.

---

# Backup strategy

Current status:

- work deployment is live;
- daily PostgreSQL backup automation is an immediate stabilization task;
- restore testing is required.

Recommended next steps:

- daily PostgreSQL backups;
- backup retention policy;
- backup location outside application directory;
- restore test procedure;
- optional VPS-level backup after production validation.

Example future backup command:

```bash
pg_dump -U receivables_user -d receivables_work > backups/receivables_work_YYYY_MM_DD.sql
```

Do not store database passwords in backup scripts or documentation.

---

# Monitoring / logs

Current:

- systemd restart policy enabled;
- logs available via journalctl;
- Nginx config can be checked before reload;
- Certbot renewal can be verified with dry run.

Useful commands:

```bash
sudo systemctl status receivables-demo --no-pager
sudo systemctl status receivables-work --no-pager
journalctl -u receivables-demo -f
journalctl -u receivables-work -f
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager
sudo systemctl status postgresql --no-pager
sudo certbot certificates
sudo certbot renew --dry-run
```

Production improvements:

- structured application logging;
- ETL run logs;
- ingestion status table;
- failed-load alerts;
- backup logs.

---

# Production MVP v1 checklist

Completed:

- [x] Create isolated work application directory.
- [x] Create isolated work PostgreSQL database.
- [x] Configure work `.env` on server.
- [x] Restore real work snapshots into `receivables_work`.
- [x] Configure `receivables-work` systemd service.
- [x] Configure `work.maximvenevtsev.com` DNS record.
- [x] Configure Nginx reverse proxy on port `8081`.
- [x] Enable Nginx Basic Auth.
- [x] Enable HTTPS with Let's Encrypt.
- [x] Create post-deploy config backups.
- [x] Add work UI hardening: latest snapshot date, browser title and favicon.
- [x] Tag release as `work-deploy-v1`.
- [x] Implement Mail Gateway.
- [x] Implement Orchestrator.
- [x] Validate end-to-end automation locally.

---

# Immediate production-hardening steps

1. Add daily PostgreSQL backups for `receivables_work`.
2. Perform and document a restore test.
3. Deploy Automation Layer configuration to VPS.
4. Enable cron or systemd timer scheduling after dry-run validation.
5. Rotate deployment and Basic Auth passwords.
6. Optionally replace HTTPS-token deploy access with an SSH deploy key.
7. Add automation health checks, monitoring and alerting.
8. Review backup retention and raw-file retention policy.
