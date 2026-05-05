# ARS Debt Management BI

Production-style data pipeline and dashboard for receivables management.

---

## 🚀 What problem it solves

This project transforms raw receivables reports into a structured analytical system:

- Full visibility of accounts receivable
- Identification of overdue debt
- Prioritization of collection actions
- Drill-down to invoice level
- Aging analysis (0–7 / 7–30 / 30+ days)
- Daily snapshot tracking for trend analysis

---

## 🧠 Key idea

Instead of working with static Excel reports:

➡️ We build a **data pipeline + analytical layer + interactive UI**


TXT / Excel → Python ingestion → PostgreSQL → Analytical Views → NiceGUI Dashboard


---

## ⚙️ Architecture

### Data ingestion
- Source: Axapta-generated TXT / Excel reports
- Parsing and normalization via Python
- Validation layer (data quality checks)
- Snapshot-based storage

### Storage
- PostgreSQL database
- Fact table: receivables snapshot
- Historical accumulation (daily snapshots)

### Analytics layer
- SQL views:
  - `v_dashboard_overview`
  - `v_branch_summary`
  - `v_client_priority`
  - `v_client_deltas`

### Frontend
- NiceGUI (Python-based UI)
- Fully interactive dashboard
- Drill-down navigation

---

## 📊 Features

### Dashboard
- Total debt
- Overdue debt (% included)
- Due today
- High-risk clients
- Branch-level breakdown
- Clickable filtering

### Overdue page
- Focus on problematic clients
- Action recommendations:
  - CALL NOW
  - CONTROL TODAY
  - REMIND
  - MONITOR

### Client card (PRO level)
- Client profile (name, group, parent org)
- KPI summary
- Aging structure visualization
- Invoice-level drill-down
- Overdue highlighting

---

## 📈 Aging analysis

Each client is analyzed by overdue buckets:

- Not overdue
- 1–7 days
- 8–30 days
- 31+ days

With:
- Amount
- Share of total debt
- Visual distribution

---

## 🔮 Future roadmap

See: `docs/FUTURE_ROADMAP.md`

Planned features:
- Client payment discipline rating
- Parent organization analytics
- Cash flow forecasting
- CRM-like action tracking

---

## 🛠️ Tech stack

- Python 3.13
- pandas
- SQLAlchemy
- PostgreSQL
- NiceGUI

---

## ▶️ How to run

```bash
python -m src.app.main

Open:

http://localhost:8080