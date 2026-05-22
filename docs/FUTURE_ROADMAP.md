# Future Roadmap

## Client payment discipline rating

Current status:
- first configurable rating engine implemented
- rating rules are stored in YAML
- rules are loaded into PostgreSQL
- rating is calculated from historical snapshots
- current confidence is marked as LOW until enough history is accumulated
- rating is displayed across major operational UI tables

Future versions may include a client rating model based on historical payment behavior.

Possible rating levels:

- 5 stars: no overdue debt during the period
- 4 stars: rare technical delays of 1–2 days and low overdue share
- 3 stars: occasional overdue payments, but generally manageable
- 2 stars: regular overdue payments
- 1 star: high-risk client with persistent overdue debt

Potential metrics:

- average overdue days
- maximum overdue days
- overdue frequency percentage
- overdue amount share
- number of overdue episodes
- payment discipline trend
- debt volatility
- recurring cash gap indicators

## Rating severity weighting

Future versions may include severity weighting for client ratings:

- reduce impact of very small overdue balances
- increase downgrade impact for large overdue debt
- distinguish technical overdue amounts from material collection risk
- include overdue amount thresholds in configurable rating rules

## Rating history and trend analysis

Future versions may include rating dynamics:

- rating changes over time
- downgrade / upgrade alerts
- rating trend chart on client card
- parent-organization-level rating aggregation
- branch-level rating distribution
- historical rating audit trail

## Parent organization analysis

Future versions may include analysis by parent organization:

- total debt by parent organization
- overdue debt by parent organization
- linked clients under the same parent organization
- cross-client risk inside one parent structure

## Cash flow forecasting

Future versions may include expected incoming payments:

- due today
- due in 3 days
- due in 7 days
- expected payment reliability by client
- expected vs actual payment comparison

## Comments and action tracking

Future versions may include a simple CRM-like workflow:

- next action
- responsible manager
- last contact date
- promised payment date
- comment history

## Multi-currency receivables

Future versions may include multi-currency support:

- separate KPI cards for RUR and EUR debt
- currency-specific overdue amounts
- currency-specific branch summaries
- optional FX conversion logic
- hiding EUR blocks when no EUR-denominated debt exists