# Future Roadmap

## Client payment discipline rating

Current status:
- first configurable rating engine implemented
- rating rules are stored in YAML
- rules are loaded into PostgreSQL
- rating is calculated from historical snapshots
- rating history snapshots are stored after ingestion
- rating dynamics are available for clients
- weighted portfolio rating is available for parent organizations and branches
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

Current status:
- client rating history table implemented
- automatic daily rating snapshot creation implemented
- client rating dynamics view implemented
- latest rating dynamics view implemented
- rating change events view implemented
- parent-organization weighted portfolio rating implemented
- branch weighted portfolio rating implemented
- reusable rating dynamics UI component implemented

Future versions may include:

- dedicated rating trend chart on client card
- downgrade / upgrade alert queue
- executive rating quality dashboard
- rating migration matrix
- branch and parent organization benchmarking
- historical rating audit screen

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

## Notification system

Future versions may include operational notification workflows:

- configurable email reminders
- reminder rules based on client rating
- payment deadline notifications
- escalation workflows
- operational notification queue
- automatic reminder scheduling

## Client communication layer

Future versions may include operational communication tracking:

- client email storage
- manual communication notes
- collection interaction history
- promised payment tracking
- next-action reminders
- communication timeline

## Payment term analytics

Future versions may include advanced payment-term analysis:

- effective payment term calculation
- contractual vs actual payment behavior
- dynamic payment term adjustments
- client payment discipline profiling
- historical payment-term volatility
- operational payment-term exceptions

## Branch operational analytics

Current status: branch analytics card implemented with historical debt charts, debt structure visualization, period filtering and behavioral indicators.

Future versions may include deeper branch-level operational monitoring:

- branch operational scorecards
- branch overdue benchmarking
- branch collection efficiency comparison
- branch risk heatmaps
- branch trend analysis
- branch workload monitoring

## Green debt quality monitoring

Purpose:

Detect cases where collection risk is hidden inside non-overdue debt through extended payment terms, manual due-date movement or abnormal contractual exceptions.

The objective is to identify hidden portfolio deterioration before it appears in overdue buckets.

Current concept includes:

### Executive-level monitoring

- historical distribution of green debt by payment-term buckets:
  - 0–30 days
  - 31–60 days
  - 61–90 days
  - 91–120 days
  - 120+ days

- historical green-debt maturity trend
- long-term green exposure indicators
- green debt concentration risk
- hidden-risk exposure monitoring
- executive alerts for abnormal portfolio shifts

## Executive Analytics

- Детализация управленческих сигналов:
  - Long Green Debt
  - Overdue Debt
  - Hidden Risk
  - Branch Health

- Контроль ручного изменения сроков оплаты
  (term shift detection)

- Bubble Matrix:
  рейтинг × срок отсрочки × сумма

### Branch-level monitoring

Future Branch Card enhancements:

- branch green-debt maturity structure
- branch comparison by payment-term profile
- branch hidden-risk score
- branch long-term exposure indicators

Additional analytical tables:

- top clients with 90+ day green debt
- top clients with 120+ day green debt
- branch-level hidden-risk ranking

### Client-level monitoring

Future Client Card enhancements:

- invoice payment-term visibility
- typical client payment term calculation
- abnormal payment-term detection
- payment-term exception highlighting

Risk signals:

- payment term > typical client term
- payment term > 60 days
- payment term > 90 days
- payment term > 120 days

Potential visual indicators:

- WARNING
- HIGH RISK
- CRITICAL

### Historical payment-term analytics

Future analytical capabilities:

- historical payment-term distribution
- payment-term drift monitoring
- abnormal term-extension detection
- contractual-term vs actual-term analysis
- hidden-risk migration tracking

### Hidden-risk detection logic

Examples of suspicious patterns:

- increasing share of 90+ day green debt
- increasing share of 120+ day green debt
- rapid deterioration of green-debt maturity structure
- concentration of long-term exposure in a small number of clients
- repeated payment-term extensions for the same client

Purpose:

Detect hidden portfolio deterioration before it becomes overdue debt.

## Operational workflow automation

Future versions may include operational automation:

- priority queue generation
- automatic client escalation
- smart operational sorting
- collection workload balancing
- configurable operational rules
- action recommendation engine

## Real production deployment

Current status:
- isolated local work database implemented
- demo VPS deployment implemented
- separate work environment architecture implemented
- production deployment preparation in progress

Next planned steps:

- protected production deployment
- scheduled ETL execution
- backup automation
- operational logging
- user management
- authentication layer
- deployment automation

## Frontend architecture evolution

Future frontend improvements may include:

- reusable dashboard widgets
- configurable operational layouts
- persistent filter state
- role-based UI customization
- responsive mobile operational views
- advanced chart widgets
- operational dark mode

## Executive Overview Dashboard

- executive-level AR portfolio overview
- historical portfolio quality trends
- weighted portfolio rating
- overdue dynamics analytics
- rating-bin exposure structure
- concentration risk indicators
- branch health heatmap
- top risk exposure monitoring
- abnormal trend detection
- executive summary insights


## Phase 2 completed

Implemented historical analytics layer:

- client historical debt analytics
- parent organization historical debt analytics
- branch historical debt analytics
- reusable historical charts
- historical KPI summaries
- behavioral indicators
- reactive period filtering
- hierarchical drill-down analytics

## PHASE 3 — Advanced Behavioral Risk Analytics

Now that Phase 2 historical analytics is implemented, the next analytical step is advanced behavioral risk modeling.

Planned features:

- Rating trend visualization
- Downgrade / upgrade alerts
- Payment behavior analysis
- Behavioral anomaly detection
- Predictive collection risk indicators
- Branch-level risk benchmarking
- Parent organization risk aggregation
- Executive portfolio quality monitoring
- Green debt quality monitoring