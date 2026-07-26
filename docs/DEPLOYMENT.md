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

- Production Foundation v1 is live;
- release tag: `work-deploy-v1`;
- protected by Nginx Basic Auth;
- uses real operational data;
- contains real receivables snapshots;
- dashboard displays the latest snapshot date as `Данные обновлены: dd.mm.yyyy`;
- browser title is `Кофточки+`;
- favicon is enabled.
- production Mail Gateway and Orchestrator run hourly;
- the online database and dashboard refresh through the existing ingestion pipeline;
- the production source archive is exposed to Local Sync through a persistent read-only, chrooted SFTP-only path.

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
- every final archived report must be explicitly published with mode `0644`;
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
- Final archive publication applies file mode `0644` after the move completes; directory permissions are unchanged.
- PostgreSQL and the dashboard are updated only through the existing ingestion and SQL view layers.

Mail Gateway and Orchestrator do not modify parsing, mapping, rating or SQL business logic.

## Recommended deployment order

1. Deploy code.
2. Create runtime directories.
3. Configure `.env`.
4. Dry-run Mail Gateway.
5. Dry-run Orchestrator.
6. Run one real execution.
7. Enable and validate the hourly scheduler.

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

Scheduling requirement:

- production orchestration runs hourly;
- only one run may operate at a time;
- scheduler output is retained in the production logging path;
- failed runs require operator review;
- scheduler configuration remains server-side and must not contain secrets.

## Production archive access for Local Sync

Production reports are synchronized through a dedicated read-only boundary:

```text
production archive
    → persistent read-only bind mount
    → chrooted SFTP-only identity
    → Local Sync on Windows
```

Security requirements:

- the synchronization identity has no shell;
- the identity cannot upload, rename, delete or create remote files/directories;
- the chroot exposes only the intended read-only archive view;
- the underlying archive remains owned and written by the production pipeline;
- archive directories retain their existing restrictive permissions;
- final report files are mode `0644` so the read-only SFTP process can read them;
- host keys and private keys are never committed.

Validate the mount after a server restart:

```bash
mountpoint <read-only-archive-mount>
findmnt <read-only-archive-mount>
```

Confirm the mount reports read-only options. Perform upload/delete denial tests only with a harmless test target and never against production reports.

## Local Sync configuration

Local `.env` values use environment-specific values and must not be committed:

```dotenv
LOCAL_SYNC_SSH_HOST=
LOCAL_SYNC_SSH_PORT=22
LOCAL_SYNC_SSH_USER=
LOCAL_SYNC_SSH_IDENTITY_FILE=
LOCAL_SYNC_REMOTE_ARCHIVE_DIR=
LOCAL_SYNC_INBOX_DIR=data/local_sync_inbox
LOCAL_SYNC_MANIFEST_PATH=data/local_sync_manifest.json
LOCAL_SYNC_LOG_PATH=data/local_sync_logs/local_sync.jsonl
LOCAL_SYNC_RAW_DIR=data/raw_work
LOCAL_SYNC_ARCHIVE_DIR=data/archive_work
LOCAL_SYNC_FAILED_DIR=data/failed_work
LOCAL_SYNC_ALLOWED_EXTENSIONS=.txt
LOCAL_SYNC_CONNECT_TIMEOUT_SECONDS=30
```

`LOCAL_SYNC_RAW_DIR` and `RAW_DIR` must resolve to the same local directory. Local development never reads Yahoo and never copies the production database; it rebuilds history through source reports and the existing ingestion pipeline.

## Manual local synchronization

Local synchronization is deliberately manual. From the project virtual environment:

```powershell
python -m src.automation.local_sync.cli --dry-run --order oldest
python -m src.automation.local_sync.cli --order oldest
```

Double-click launchers:

```text
scripts/sync_local_dry_run.cmd
scripts/sync_local.cmd
```

The CMD wrappers invoke their matching PowerShell script with `-NoProfile` and `-ExecutionPolicy Bypass`. The PowerShell launchers:

- resolve the project virtual-environment Python;
- resolve the Local Sync key from the current Windows user profile;
- require the Windows `ssh-agent` service;
- check whether that specific key fingerprint is already loaded;
- request key unlocking through `ssh-add` only when required;
- retain the console window and propagate the Local Sync exit code.

The dry-run launcher passes `--dry-run`, so it does not write files, repair manifests, hand off reports or run ingestion.

First-run Windows preparation:

1. Install/enable the Windows OpenSSH Client.
2. Verify the server host fingerprint through the approved operational channel.
3. Place the dedicated private key in the expected user-profile SSH location.
4. Start `ssh-agent` from an administrator session if required.
5. Run the dry-run launcher.
6. Review the plan before running normal synchronization.

## Local Sync troubleshooting

### `ssh-agent` is not running

Start and configure the Windows service from an administrator PowerShell session, then rerun the launcher. Do not place a plaintext key passphrase in a script or `.env`.

### The key is not loaded

The launcher checks the expected key fingerprint and invokes `ssh-add` when needed. If loading fails, verify the local key file and agent state; do not copy private-key contents into logs or support messages.

### Stale Local Sync lock

First confirm that no Local Sync Python process is running. Only then remove the configured local manifest lock file. Never remove a lock while another synchronization may still be active.

### Permission denied while downloading an archive file

On production, verify:

- the read-only bind mount is present and mounted read-only;
- the SFTP identity can traverse the chrooted archive path;
- the final report file has mode `0644`;
- parent-directory permissions and ownership still match the approved SFTP design.

Do not grant write access or broaden directory permissions to solve a file-read problem.

### Logs and manifest

Default local runtime locations:

```text
data/local_sync_logs/local_sync.jsonl
data/local_sync_manifest.json
data/local_sync_inbox
```

These files are operational artifacts, may contain source metadata and must remain ignored. A corrupt manifest is timestamp-preserved and rebuilt by hashing eligible files in local inbox/raw/archive/failed directories.

---

# Historical Backfill maintenance

The Historical Backfill Framework is an exceptional maintenance workflow for
approved historical report batches. It is not part of the scheduler and must
not be substituted for normal daily ingestion.

## Required safeguards

Before any write-mode run:

1. Confirm the report batch and approved checksums through the framework's
   dry-run output.
2. Take a PostgreSQL backup of the target database.
3. Verify that the backup completed successfully and that the restore procedure
   is understood.
4. Pause the ingestion scheduler and confirm that no ingestion process is
   active.
5. Confirm the target database and environment explicitly.
6. Preserve the original source files unchanged.
7. Retain the dry-run and final verification output with the maintenance record.

Do not run historical maintenance concurrently with Mail Gateway handoff,
scheduled ingestion, Local Sync ingestion or another backfill session.

## Dry-run workflow

Run preflight first:

```bash
python -m src.ingestion.historical_backfill \
  --source-dir "<approved-report-directory>" \
  --dry-run
```

Dry-run parses and validates the complete batch, verifies audited source
checksums, inspects database metadata and checks structural invariants. It does
not open a write transaction.

Stop if dry-run reports:

- a missing or unapproved file;
- checksum, parser, date or row-count mismatch;
- a validation error outside an explicitly approved exception;
- mixed or conflicting database state;
- incomplete history without a deliberate rebuild request;
- history later than the latest fact date;
- a current-snapshot view that does not resolve to the latest fact date;
- a persistent maintenance object.

## Controlled execution

After backup, scheduler pause and successful dry-run:

```bash
python -m src.ingestion.historical_backfill \
  --source-dir "<approved-report-directory>"
```

If all approved facts already match available database metadata but history
requires deliberate reconstruction:

```bash
python -m src.ingestion.historical_backfill \
  --source-dir "<approved-report-directory>" \
  --rebuild-history
```

The framework loads and reconstructs the batch in one transaction. It processes
facts chronologically, stages base rating and Credit Quality results for the
affected suffix, verifies coverage, and replaces history only after staging is
complete.

## Verification queries

Replace the example start date with the approved batch boundary.

Fact coverage:

```sql
SELECT
    report_generated_date,
    COUNT(*) AS fact_rows,
    COUNT(DISTINCT load_id) AS loads,
    COUNT(DISTINCT source_file_name) AS source_files
FROM core.receivables_snapshot_fact
WHERE report_generated_date >= DATE 'YYYY-MM-DD'
GROUP BY report_generated_date
ORDER BY report_generated_date;
```

Fact client/date pairs missing base rating history:

```sql
SELECT DISTINCT f.report_generated_date, f.client_id
FROM core.receivables_snapshot_fact f
LEFT JOIN core.client_rating_history h
  ON h.snapshot_date = f.report_generated_date
 AND h.client_id = f.client_id
WHERE f.report_generated_date >= DATE 'YYYY-MM-DD'
  AND h.client_id IS NULL
ORDER BY f.report_generated_date, f.client_id;
```

Rated fact client/date pairs missing Credit Quality history:

```sql
SELECT DISTINCT f.report_generated_date, f.client_id
FROM core.receivables_snapshot_fact f
JOIN core.client_rating_history r
  ON r.snapshot_date = f.report_generated_date
 AND r.client_id = f.client_id
LEFT JOIN core.client_credit_quality_history cq
  ON cq.snapshot_date = f.report_generated_date
 AND cq.client_id = f.client_id
WHERE f.report_generated_date >= DATE 'YYYY-MM-DD'
  AND cq.client_id IS NULL
ORDER BY f.report_generated_date, f.client_id;
```

Duplicate client/date history rows:

```sql
SELECT 'rating' AS history_type, snapshot_date, client_id, COUNT(*) AS rows
FROM core.client_rating_history
GROUP BY snapshot_date, client_id
HAVING COUNT(*) > 1
UNION ALL
SELECT 'credit_quality', snapshot_date, client_id, COUNT(*)
FROM core.client_credit_quality_history
GROUP BY snapshot_date, client_id
HAVING COUNT(*) > 1;
```

Credit Quality rows without same-date base rating:

```sql
SELECT cq.snapshot_date, cq.client_id
FROM core.client_credit_quality_history cq
LEFT JOIN core.client_rating_history r
  ON r.snapshot_date = cq.snapshot_date
 AND r.client_id = cq.client_id
WHERE r.client_id IS NULL;
```

Latest-fact and production-view resolution:

```sql
SELECT
    (SELECT MAX(report_generated_date)
     FROM core.receivables_snapshot_fact) AS latest_fact_date,
    (SELECT MAX(report_generated_date)
     FROM core.v_receivables_current_snapshot) AS current_view_date;
```

History later than the latest fact:

```sql
WITH latest AS (
    SELECT MAX(report_generated_date) AS snapshot_date
    FROM core.receivables_snapshot_fact
)
SELECT 'rating' AS history_type, COUNT(*) AS rows,
       MIN(h.snapshot_date) AS earliest, MAX(h.snapshot_date) AS latest
FROM core.client_rating_history h, latest
WHERE h.snapshot_date > latest.snapshot_date
HAVING COUNT(*) > 0
UNION ALL
SELECT 'credit_quality', COUNT(*), MIN(h.snapshot_date), MAX(h.snapshot_date)
FROM core.client_credit_quality_history h, latest
WHERE h.snapshot_date > latest.snapshot_date
HAVING COUNT(*) > 0;
```

All discrepancy queries must return no rows, and the latest fact and current
view dates must match before the scheduler is resumed.

## Rollback and recovery

Parser, load, maintenance SQL or verification failure aborts the shared
transaction. PostgreSQL restores snapshot metadata, facts and both history
tables to their pre-run state.

If verification fails after a successful commit:

1. Keep the scheduler paused.
2. Preserve command output and database logs.
3. Do not make ad hoc table edits.
4. Restore the pre-maintenance backup through the approved restore procedure.
5. Re-run the verification queries before resuming normal ingestion.

The framework does not modify production views and does not install persistent
snapshot-context functions or migrations.

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
- [x] Deploy production Mail Gateway and Orchestrator.
- [x] Schedule hourly production ingestion.
- [x] Validate automatic PostgreSQL and online dashboard refresh.
- [x] Establish the production source-report archive.
- [x] Publish final archive files with mode `0644`.
- [x] Configure persistent read-only archive exposure.
- [x] Configure dedicated chrooted SFTP-only access with no shell/write permission.
- [x] Implement restart-safe Local Sync with SHA256 identity.
- [x] Validate atomic download and RAW handoff.
- [x] Add manual normal and dry-run Windows launchers.
- [x] Validate production-to-local ingestion and dashboard parity.

---

# Immediate production-hardening steps

1. Add daily PostgreSQL backups for `receivables_work`.
2. Perform and document a restore test.
3. Add automation health checks, monitoring and failure notifications.
4. Add an operational status page and dashboard-freshness checks.
5. Define application-level roles beyond current perimeter authentication.
6. Review backup retention and raw/archive retention policy.
7. Begin Performance Engineering and establish production baselines.
