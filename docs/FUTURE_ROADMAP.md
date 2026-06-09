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

## Credit-quality rating evolution

Current rating model is primarily based on overdue debt behavior.

Future versions should gradually evolve from a pure overdue-based rating into a broader credit-quality rating model.

Planned analytical dimensions:

### Payment discipline

- overdue frequency
- overdue amount share
- average overdue days
- maximum overdue days
- overdue episode count

### Payment-term quality

- weighted average payment term
- maximum payment term
- share of debt with payment terms above 45 days
- share of debt with payment terms above 90 days
- share of debt with payment terms above 120 days

### Term-shift behavior

- number of due-date extensions
- frequency of manual due-date changes
- average extension length
- recurring extension patterns

Target objective:

Detect clients that formally remain outside overdue buckets but systematically require excessive payment terms or repeated due-date extensions.

Long-term vision:

Rating should represent overall credit quality rather than overdue behavior only.

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

## Invoice lifecycle analytics

Current status:
- invoice lifecycle views implemented
- estimated payment events detected from snapshot disappearance
- partial payment events detected from open-balance decrease
- active invoices are excluded from full-payment detection
- invoice payment events are available for client-level drill-down

Derived metrics:

- contractual payment term
- actual payment term
- delay vs original due date
- delay vs latest due date
- number of due-date extensions
- cumulative extension days

Purpose:

Provide full transparency into how individual invoices move through the collection process and identify hidden collection risks.

## Paid invoice analytics

Current status:
- recent payment events block implemented on Client Card
- last 20 payment events displayed
- full and partial payments supported
- estimated payment date shown
- actual payment term calculated
- delay vs due date highlighted
- term-shift markers shown for paid/partially paid invoices

Future improvements may include:
- configurable period filter
- client-level payment behavior KPIs
- aggregation by analytics type
- paid invoice trend chart

Client-level metrics:

- average contractual payment term
- average actual payment term
- average payment delay
- maximum payment delay
- percentage of invoices paid on time
- percentage of invoices with due-date extensions
- extension frequency
- extension severity

Purpose:

Evaluate actual payment behavior rather than only currently open receivables.

This analytical layer will serve as the foundation for future behavioral risk models and credit-quality ratings.

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

Future versions may include monitoring of non-overdue debt quality.

Potential capabilities:

- distribution of non-overdue debt by payment terms
- distribution by deferred payment periods
- branch-level comparison of payment-term structure
- historical term-shift analysis
- abnormal payment-term extension detection
- hidden-risk exposure monitoring
- control of artificially preserved “green zone” debt

Purpose:

Detect cases where high-risk debt is kept outside overdue buckets through manual payment-term extensions or artificial due-date movement.

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

Current status:
- executive overview page implemented
- portfolio KPI cards implemented
- portfolio status / verdict implemented
- historical portfolio quality charts implemented
- green debt maturity structure implemented
- weighted payment-term trend implemented
- rating-bin exposure chart implemented
- management signal cards implemented
- drill-down pages implemented:
  - `/executive/long-green`
  - `/executive/overdue`
  - `/executive/branches`
  - `/executive/hidden-risk`
  - `/executive/term-shifts`

Implemented analytical focus:
- executive-level AR portfolio overview
- historical portfolio quality trends
- weighted portfolio rating
- overdue dynamics analytics
- rating-bin exposure structure
- concentration risk indicators
- branch health monitoring
- top risk exposure monitoring
- hidden-risk client detection
- green debt quality monitoring
- executive summary insights
- term-shift detection for manual due-date extensions

Next improvements:
- bubble matrix: rating × payment term × amount
- branch-level green debt maturity visualization
- long-green drill-down filtering and top-client summaries
- hidden-risk scoring refinement
- portfolio credit-quality score
- payment-term quality monitoring
- rating quality vs payment-term matrix
- hidden-risk migration tracking
- concentration of long-term green debt
- executive client risk segmentation


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
- Credit-quality rating model
- Invoice lifecycle analytics
- Paid invoice behavior analytics
- Term-shift risk scoring
- Hidden-risk client classification
- Effective payment behavior profiling

## Credit exposure analytics

Future versions may include credit exposure monitoring and credit-limit recommendations.

Potential capabilities:

- effective working exposure calculation
- recommended credit limit
- credit-limit utilization monitoring
- abnormal shipment detection
- exposure growth monitoring
- concentration risk analysis
- safe next-shipment recommendation

Derived metrics:

- average exposure during payment-term window
- maximum historical exposure
- exposure volatility
- exposure growth rate
- utilization percentage

Purpose:

Provide practical credit-control recommendations and support shipment approval decisions.

## Collection efficiency analytics

Future versions may include collection performance monitoring.

Potential metrics:

- overdue recovery rate
- average overdue resolution time
- overdue backlog dynamics
- manager workload monitoring
- action effectiveness tracking
- promised-payment fulfillment rate

Purpose:

Measure operational effectiveness of collection activities.

## User-defined branch groups

Future versions may include reusable branch group definitions.

Potential capabilities:

- saved branch selections
- personal branch groups
- shared branch groups
- regional management views
- quick-filter presets

Purpose:

Support recurring operational and regional analysis workflows.

## Data quality and governance

Future versions may include automated data-quality controls.

Potential capabilities:

- missing due-date detection
- invoice duplication checks
- branch-classification validation
- parent-organization consistency checks
- payment-term anomaly detection
- ingestion quality dashboard
- data-quality scoring

Purpose:

Ensure analytical outputs remain trustworthy as the system scales.