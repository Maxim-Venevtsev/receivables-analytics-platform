# DATA MODEL

## Core table

### core.receivables_snapshot_fact

Snapshot-based operational receivables storage.

---

## Historical analytics views

- v_client_daily_history
- v_parent_org_daily_history
- v_branch_daily_history

---

## Hierarchical structure

Branch
    ↓
Parent Organization
    ↓
Client
    ↓
Invoice

---

## Historical analytics metrics

- total debt
- normal debt
- due soon debt
- due today debt
- overdue debt
- overdue share
- maximum overdue days