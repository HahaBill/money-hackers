# Autonomous Financial Analyst Agent
### PRD v4

**Guiding principle:** computed facts first, agent intelligence second, voice last.
Every number the owner sees is traceable to arithmetic over their own transactions. Every causal claim is traceable to evidence that discriminates between hypotheses.

---

## 0. Reading guide

| If you are | Read |
|---|---|
| Building the engine | §5 to §16 |
| Building the investigation agent | §17 to §20 |
| Building the UI | §21 |
| Building voice | §22 |
| Building eval / PRISM | §23 to §25 |
| Generating test data | §26 |
| Managing the build | §27 to §30 |

---

## 1. Objective

An autonomous financial-analysis agent for a small business (café for the hackathon) that runs on every new period without being prompted and:

1. Detects what changed and what is going wrong
2. Quantifies impact with an exact-sum attribution to business drivers
3. Names the specific counterparties, SKUs and line items concentrating that impact
4. Scores anomalies against the business's own historical distributions, not against percentage thresholds
5. Flags spend that has moved beyond what market conditions explain, phrased as verification, never accusation
6. Generates hypotheses, gathers discriminating evidence (internal first, external when needed), and rejects what the evidence does not support
7. Simulates candidate actions through the driver graph and ranks them by modeled leverage with stated assumptions
8. Issues per-driver targets for next period with a direction indicator
9. Asks the owner the two or three questions whose answers would close the largest unexplained dollar gaps
10. Revises its own earlier explanations when later periods contradict them, on the record
11. Delivers all of the above through a dashboard, a traversable reasoning graph, and an ElevenLabs voice agent that share one verified state

The track asks: what changed, why, what is driving it. The deliverable answers those and adds: what to do, what to verify, what I got wrong last time.

---

## 2. Changes from v3

| Area | v3 | v4 |
|---|---|---|
| Revenue side | volume / price / mix | full funnel: traffic × conversion × basket × price × mix; traffic-revenue gap explained |
| Leverage basis | gross profit | contribution, with declared variable share per opex leaf |
| Materiality | raw product | gated, log-scaled dollars, bounded factors, persistence as boost, concentration term, cross-period rescale |
| Persistence | category-level | attribution-level via `recurs_from`, same leaf and top contributor |
| Proactive detection | variance only | relationship-rules layer (§13b) that fires on broken metric relationships |
| Cash / accrual | boolean check | cutoff-window adjustment policy with audit tags |
| Ingest | raw fields | derived features: recurrence key, counterparty normalization, basis, hour bucket |
| Learning | answers + directive scoring | owner right / wrong / incomplete feedback feeding template priors; analog retrieval |
| Residual | not discussed | explicit statement of why Shapley has none |
| Critique log | absent | Appendix A |

### Changes from v2

| Area | v2 | v3 |
|---|---|---|
| Priors | illustrative table | grounded in published café benchmarks, with variance rationale |
| Baselines | mean / sd | robust (median / MAD) with shrinkage, n-aware |
| Investigation protocol | loop outline | full hypothesis templates, evidence scoring, belief update, verdict rules |
| Tavily | good/bad example | query templates per hypothesis class, parameter settings, corroboration scoring, source tiers |
| ElevenLabs | modes described | agent config, server tools, dynamic variables, guardrails, post-call webhook |
| PRISM | trace tree + tests | named metrics, regression harness, scoring rubric, failure taxonomy |
| Synthetic data | mentioned | full generator spec with scenario parameters |
| Repo | absent | module layout, interfaces, run commands |
| Build plan | priorities | hour-by-hour with cut lines |
| Risks | chat note | failure-mode table with mitigations |
| Research frontier | absent | §31 |

---

## 3. Required technologies

### GIDE (mandatory)
All build, test and refactor work in GenerativeIDE. Use `--continue` / `--resume` for multi-step sessions. Local Ornith 1.0 9B for cheap classification and templating steps (hypothesis class selection, query rewriting); cloud model (Claude) for evidence evaluation, verdicts, narrative, and revision. Keep the JSONL action logs; they are part of the "how we built it" story.

```
gide -p "implement shapley decomposition over the café driver graph with exact-sum test"
gide --continue -p "add concentration analysis at transaction grain"
```

### PRISM (mandatory)
`pip install prismtrace-sdk`. Builder code `MONEYTALKS#1`. Run the agent once with tracing before the main build flow so traces exist. Used as Observe → Improve → Prove. Full design in §23 to §25.

### ElevenLabs (mandatory)
Agents Platform. The voice agent calls the analysis backend through server tools and never computes. Full design in §22.

### Tavily (optional, used)
Triggered by a concrete hypothesis about an observed variance. Full design in §19.

---

## 4. Architecture

```
                         ┌──────────────────────────────┐
                         │  Reasoning & Calculation Graph│  ← written by every stage
                         │  (persistent, cross-period)   │
                         └──────────────▲───────────────┘
                                        │
Ingest → Reconcile → Metric Engine → Baselines → Variance → Shapley → Concentration
   │        │ (DuckDB, full history)      │                              │
   │   ANALYSIS_BLOCKED                   │                              ▼
   │                                      │                     Materiality Ranking
   │                                      │                              │
   │                                      ▼                              ▼
   │                            Anomaly + Leakage Scan            Sensitivity Engine
   │                                      │                              │
   │                                      └──────────┬───────────────────┘
   │                                                 ▼
   │                                    Investigation Agent (LLM)
   │                                    hypotheses → internal evidence → Tavily → verdict
   │                                                 │
   │                                                 ▼
   │                          Recommendation Simulation → Target Directives
   │                                                 │
   │                                                 ▼
   │                        Structured Findings + Open Questions + Revisions
   │                                                 │
   │                                  validate every figure against node ids
   │                                                 │
   │                    ┌────────────────┬───────────┴────────┬────────────────┐
   │                    ▼                ▼                    ▼                ▼
   │               Dashboard        Graph View          ElevenLabs         PRISM
   │                                                    (server tools)     (trace)
```

### Responsibility split

| Layer | Owns | Never does |
|---|---|---|
| Python / SQL / DuckDB | arithmetic, metrics, variance, Shapley, concentration, baselines, z-scores, leakage rules, sensitivity, simulation, directive math, output validation | narrative |
| LLM agent | prioritization among ranked drivers, hypothesis generation from templates, investigation planning, tool selection, evidence weighing, question formulation, narrative, revision | any arithmetic, any figure not in the graph |
| ElevenLabs | spoken briefing, spoken follow-up, capturing owner answers | computing, introducing figures |
| PRISM | tracing, evaluation, failure analysis, regression proof | affecting runtime decisions |

---

## 5. Canonical data model

```python
@dataclass
class Transaction:
    txn_id: str            # stable hash of (source_file, row_index) if absent
    date: date
    period: str            # "2026-08"
    amount: Decimal        # signed: revenue positive, cost negative
    txn_type: Literal["revenue", "cogs", "opex", "transfer", "other"]
    category: str          # mapped to driver-graph leaf, see §7
    counterparty: str | None
    product: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    source_row: int
    ingested_at: datetime
    # derived at ingest, never by the LLM
    day_of_week: int
    hour_bucket: str | None            # "open", "peak", "close", if timestamp present
    is_recurring: bool                 # fuzzy match on counterparty + amount ±3% + cadence
    recurrence_key: str | None         # groups instances of the same recurring charge
    counterparty_id: str               # normalized: casefold, strip legal suffixes, fuzzy-merge
    basis: Literal["cash", "accrual"]  # from source file flag or inferred, see §6

@dataclass
class PeriodSummary:
    period: str
    revenue: Decimal
    expenses: Decimal
    operating_profit: Decimal
    source: str

@dataclass
class OperationalMetric:      # optional
    period: str
    foot_traffic: int | None
    orders: int | None
    opening_hours: Decimal | None
```

### Category mapping
A YAML file maps raw categories to graph leaves. Unmapped categories fail reconciliation (§6), they are not silently bucketed into "other".

```yaml
leaves:
  coffee_beans: ["beans", "coffee", "roaster", "green coffee"]
  milk:         ["milk", "dairy", "oat milk", "alt milk"]
  food:         ["pastry", "bakery", "food", "sandwich"]
  packaging:    ["cups", "lids", "packaging", "napkins"]
  labor:        ["wages", "payroll", "staff"]
  rent:         ["rent", "lease", "occupancy"]
  electricity:  ["electric", "power", "energy"]
  other_opex:   ["insurance", "software", "marketing", "repairs", "cleaning", "fees"]
```

---

## 6. Reconciliation layer

Runs before anything else. All checks produce `data` and `check` nodes in the graph so a blocked run is itself inspectable.

| Check | Rule | On fail |
|---|---|---|
| Revenue reconciles | \|Σ txn revenue − summary revenue\| ≤ max($50, 0.5%) | BLOCK |
| Expenses reconcile by category | per-category gap ≤ max($50, 1%) | BLOCK |
| No duplicate txn_id | exact | BLOCK |
| Suspected duplicate | same counterparty, amount, within 24h, distinct txn_id | WARN, feed §14 |
| Required columns | schema | BLOCK |
| Period boundaries | every txn date inside declared period | BLOCK |
| Categories mapped | every category resolves to a leaf | BLOCK |
| Cash / accrual | see policy below | ADJUST, then BLOCK if still off |
| Quantity × price consistency | \|qty × unit_price − amount\| ≤ 1% where all three present | WARN |

### Cash / accrual policy
A boolean "bases match" check false-fails constantly, because a small café's POS export is cash-timestamped and its accounting summary is usually accrual. The policy:

1. Read the basis from each file's flag; if absent, infer: a summary with an accounts-payable or accrued-expenses line is accrual, a transaction export with settlement timestamps is cash.
2. If both bases match, reconcile directly.
3. If they differ, apply a **cutoff window** before reconciling: transactions dated in the last `k` days of period t or first `k` days of t+1 (k = 5 by default) are matched against the summary of either period by counterparty and amount. Matched items are re-dated to the period the summary places them in and tagged `basis_adjusted`.
4. If the residual gap after adjustment is still above tolerance, block with the pre- and post-adjustment gaps shown, so the owner can see the window did its job or did not.
5. The analysis basis is always the summary's basis. All metrics, attributions and narrative state which basis they are on. Never mix within one run.

The `basis_adjusted` tag is carried into the graph so a judge asking "did you just move transactions until it matched" gets a precise answer: which rows, why, and what the gap was before.

Block output:

```
ANALYSIS_BLOCKED  period=2026-08
Transaction revenue does not reconcile with the monthly account summary.
  Transactions: $68,430   Summary: $72,660   Gap: $4,230 (5.8%)
Suspected cause: 14 transactions dated 2026-08-31 appear in both August and
September files (node n_chk_04). Remove duplicates or confirm period boundary.
```

A confident explanation of wrong numbers is the worst output this system can produce. Blocking is the correct behaviour and the demo should show it once.

---

## 7. Business driver graph

Defined once as arithmetic relations. Attribution, sensitivity and directives all derive from this definition. Adding a driver is adding a line here and nowhere else.

```python
GRAPH = {
  "operating_profit":   "contribution - fixed_labor - rent - electricity_fixed - other_fixed",
  "contribution":       "revenue - cogs - variable_labor - electricity_variable - other_variable",
  "gross_profit":       "revenue - cogs",                       # reported, not the leverage basis
  "revenue":            "orders * aov",
  "orders":             "traffic * conversion",                 # when traffic is present
  "aov":                "sum(share[p] * price[p] for p in products) * items_per_order",
  "cogs":               "sum(qty_used[i] * unit_cost[i] for i in inputs)",
  "qty_used[i]":        "sum(units[p] * recipe[p][i] for p in products) * (1 + waste[i])",
}
products = ["espresso", "latte", "iced_latte", "cold_brew", "drip", "pastry", "sandwich"]
inputs   = ["coffee_beans", "milk", "food", "packaging"]
```

### Revenue funnel
`revenue = traffic × conversion × AOV` is the top of the graph, and the demo scenario is the reason: traffic +15% with revenue +11% means conversion or AOV fell about 3.5%. A system that jumps straight to cost-side drivers has left an unexplained variance sitting at the top of its own funnel. When `foot_traffic` is present, `traffic` and `conversion` are separate leaves; when it is absent, they collapse into `orders` and the narrative says the split is unavailable.

### Variable versus fixed
Leverage claims about pricing only make sense against **contribution margin**, not gross margin. If labor or electricity scale with volume, a price change that shifts volume moves those lines too, and gross-margin arithmetic overstates the leverage. Each opex leaf declares a variable share:

| Leaf | Variable share | Basis |
|---|---|---|
| labor | 0.35 | casual / overtime hours scale with orders; core roster does not |
| electricity | 0.25 | equipment duty cycle scales with volume; base load does not |
| other_opex | 0.30 | card fees, consumables |
| rent | 0.00 | |

Shares are defaults, overridable per business, and estimable from history once ≥6 periods exist (regress leaf spend on orders). Sensitivity (§15) always evaluates through `contribution`. Gross profit is still reported because owners and the track brief expect it, but it is never the basis for a leverage ranking.

### Attribution leaves
These are the units Shapley operates over. Mix is a first-class leaf, not a residual, because "revenue up, profit down" is a mix story and a system that cannot isolate mix cannot explain the headline case.

| Leaf | What changes between periods | Held constant |
|---|---|---|
| `traffic` | visitors (if available) | conversion, AOV, costs |
| `conversion` | orders / traffic (if available) | traffic, AOV, costs |
| `volume` | total units sold (used when traffic absent) | prices, mix shares, unit costs |
| `price` | per-product prices | volumes, mix, unit costs |
| `mix` | product share vector | total volume, prices, unit costs |
| `items_per_order` | basket size | everything else |
| `unit_cost[i]` | per-input unit cost, one leaf per input | volumes, prices, mix |
| `usage_efficiency[i]` | input quantity per unit sold (waste, portioning) | everything else |
| `labor` | labor spend, split variable / fixed | |
| `rent` | rent | |
| `electricity` | electricity spend, split variable / fixed | |
| `other_opex` | other | |

The counterfactual evaluator `profit(leaf_state)` takes a dict of which leaves are at current-period values and which at prior-period values and computes profit through `GRAPH`. That single function is what Shapley, sensitivity and simulation all call.

---

## 8. Deterministic metric engine

DuckDB over the full history, every run. Nothing is cached as prose.

```sql
-- example: product-level revenue, margin, share, and rolling baseline
WITH by_prod AS (
  SELECT period, product,
         SUM(quantity) AS qty,
         SUM(amount)   AS revenue,
         SUM(amount) / NULLIF(SUM(quantity),0) AS avg_price
  FROM transactions WHERE txn_type='revenue'
  GROUP BY 1,2
),
shares AS (
  SELECT *, qty / SUM(qty) OVER (PARTITION BY period) AS share
  FROM by_prod
)
SELECT *,
  MEDIAN(share) OVER (PARTITION BY product ORDER BY period
                      ROWS BETWEEN 11 PRECEDING AND 1 PRECEDING) AS share_baseline
FROM shares;
```

Computed per period and stored as `metric` nodes: revenue, expenses by leaf, gross profit, operating profit, gross margin, contribution margin per product, AOV, orders, revenue per order, product revenue / units / share / unit margin, input unit cost / quantity / spend, usage ratios (ml milk per drink, g beans per shot), price index, volume index, and for each of these the period-over-period delta and the rolling baseline (§12).

---

## 9. Reasoning & Calculation Graph (RCG)

One graph across all periods and all runs. The substrate every stage writes into. Build this first.

### Storage
DuckDB tables `nodes` and `edges`, plus a JSONL append log per run for PRISM alignment. Node ids are content-addressed (`n_` + 6 hex of sha256 over type, period, label, inputs) so re-running identical inputs yields identical ids, which makes diffs between agent versions trivial.

### Node schema

```json
{
  "id": "n_7c1e04",
  "type": "attribution",
  "period": "2026-08",
  "run_id": "r_012",
  "agent_version": "v0.3.1",
  "label": "Milk unit-cost contribution to operating profit",
  "value": -930.00,
  "unit": "USD",
  "method": "shapley",
  "formula": "phi(unit_cost[milk])",
  "inputs": ["n_3a01bb", "n_91d7f2"],
  "confidence": 1.0,
  "status": "active",
  "supersedes": null,
  "provenance": "deterministic",
  "payload": {}
}
```

### Node types and provenance

| Type | Written by | Provenance | `value` |
|---|---|---|---|
| `data` | ingest | raw | scalar or row ref |
| `check` | reconciliation | deterministic | pass / warn / block |
| `metric` | engine | deterministic | scalar |
| `baseline` | §12 | deterministic | {center, scale, n, prior_weight} |
| `variance` | engine | deterministic | delta |
| `attribution` | Shapley | deterministic | φ_i |
| `concentration` | §11 | deterministic | {contributors[], hhi} |
| `anomaly` | §12 | deterministic | z, persistence |
| `leakage_flag` | §14 | deterministic | {rule, gap_dollars, counter} |
| `hypothesis` | LLM | inferred | {class, claim, prior_belief} |
| `evidence` | internal query or Tavily | retrieved | {source, tier, support, extract} |
| `belief_update` | LLM | inferred | posterior |
| `verdict` | LLM | inferred | supported / weakening / rejected / unresolved |
| `simulation` | §15 | deterministic | Δprofit, assumptions |
| `directive` | §16 | deterministic | target, direction |
| `question` | §20 | inferred | text, voi_dollars |
| `finding` | LLM | inferred | text, severity |
| `revision` | LLM | inferred | old_node → new_node, reason |

### Edge types
`derives_from`, `supports`, `contradicts`, `tests`, `answers`, `supersedes`, `recurs_from`, `simulates`, `justifies`.

### Invariants (enforced in code, tested in CI)

1. Every `finding` has a `derives_from` path to at least one `attribution`.
2. Every `attribution` has a `derives_from` path to `data`.
3. Sibling `attribution` values sum to their parent `variance` within $0.01.
4. No `verdict` of `supported` unless at least one supporting `evidence` node has `tier ≤ 2` (§19) and is not purely temporal.
5. Every numeric token in narrative or voice output maps to a node id via the validator (§21). Unmatched numbers fail the run.
6. A node with `status: superseded` has exactly one incoming `supersedes` edge.
7. `recurs_from` edges only connect nodes of the same type and label across adjacent periods.

### Why persistent and cross-period
The September run reads `recurs_from` on the electricity hypothesis, finds August's evidence and verdict, and can write a `revision` node. Revision becomes a graph operation, not a prompt trick. Memory is inspectable, the agent's changes of mind are legible, and PRISM traces align one-to-one with graph writes.

---

## 10. Variance decomposition

### Why Shapley
For revenue = price × quantity: Δrev = ΔP·Q₀ + P₀·ΔQ + ΔP·ΔQ. The interaction term must be assigned. Gradients leave it as residual. Sequential (one-at-a-time) decomposition closes exactly but is order-dependent, and order-dependence is fatal when the product is a ranking.

Shapley averages marginal contribution across all orderings. It is the unique attribution satisfying efficiency (exact sum), symmetry, null-player and additivity. With the 9 to 12 leaves in §7 this is at most 4,096 evaluations of a pure-Python arithmetic function, single-digit milliseconds.

### Implementation

```python
def shapley(leaves, profit_fn, prior, curr):
    n = len(leaves)
    phi = {l: 0.0 for l in leaves}
    for S in subsets(leaves):
        w = factorial(len(S)) * factorial(n - len(S) - 1) / factorial(n)
        base = profit_fn(state(S, prior, curr))
        for l in leaves:
            if l in S: continue
            with_l = profit_fn(state(S | {l}, prior, curr))
            phi[l] += w * (with_l - base)
    assert abs(sum(phi.values()) - (profit_fn(curr) - profit_fn(prior))) < 0.01
    return phi
```

`state(S, prior, curr)` builds a leaf-state where leaves in S take current values and all others prior values. Because `mix` is a share vector, "mix at current" means current shares applied to prior total volume.

### Nested reporting
Report at three levels: top (contribution vs fixed leaves), within contribution (funnel, price, mix, unit costs, efficiency, variable opex), and within the funnel (traffic, conversion, basket). Every level sums exactly.

```
Operating profit change             -$4,820   (n_0f3a91)
  Contribution                      -$4,140
    Traffic                         +$2,480
    Conversion                        -$570      ← traffic +15%, orders +11%
    Items per order                    +$ 0
    Price                             +$140
    Mix                             -$1,420
    Unit cost: milk                   -$930
    Unit cost: coffee beans           -$880
    Unit cost: food / packaging       -$500
    Usage efficiency                  -$ 50
    Variable labor                    -$190
    Variable electricity              -$220
  Fixed labor                         -$140
  Fixed electricity                   -$540
  Rent / other fixed                    $ 0
```

Traffic is positive and conversion is negative. That is the point: the café got busier, converted slightly worse, and the cost lines ate the rest of the gain. The narrative must mention the conversion line even though it is small, because it is the one variance the owner's own funnel model predicts and a report that skips it looks like it did not read its own graph.

### Why there is no residual bucket
Naive price × volume × mix decomposition leaves an interaction term, and finance reports usually show it as "other / residual" or quietly fold it into one line. Both are the false-precision smell. Shapley assigns the interaction term to the leaves that jointly produce it, by the unique rule satisfying efficiency, symmetry, null-player and additivity. The exact sum is not a rounding trick and not an assumption of independence; it is the property that makes the attribution defensible. The narrative says "attributed by Shapley decomposition" once, and the graph view lets a judge click the line and see the formula.

---

## 11. Concentration analysis

Attribution says which driver. Concentration says which specific thing inside it. This maps directly to the track's example ("three customers accounting for 64% of the increase").

For each material leaf, decompose to transaction grain by the natural entity (supplier for unit costs, product for mix and price, counterparty for opex) and report:

- Top-N contributors with share of the leaf's contribution, sorted by absolute dollars
- Herfindahl index `HHI = Σ share²` over contributors; `HHI > 0.25` labelled concentrated, `< 0.15` diffuse
- Recurrence: whether each top contributor was top-3 in any of the previous three periods
- Stop rule: drill one entity level deeper (supplier → SKU, product → hour bucket) only while the top-1 contributor is under 50% and HHI is under 0.5; once a single entity or tight cluster explains at least half of what is left, that is the driver and the transaction ids are the receipts

```
Unit cost: milk  -$930
  Nordic Dairy Co           -$840   90%   top-1 in Jul, Jun
  Oat Collective             -$90   10%
  HHI 0.82  concentrated

Mix  -$1,420
  iced_latte share 18%→24%  -$910   64%
  cold_brew  share  9%→12%  -$430   30%
  drip       share 22%→18%   -$80    6%
  HHI 0.51  concentrated
```

Concentrated means one conversation or one price change fixes most of it. Diffuse means structural. The narrative must say which, because the recommendation differs entirely.

---

## 12. Distributional baselines and cold start

### Robust statistics
Small-business monthly series are short (n often < 12), non-normal, and contain one-off shocks. Use median and MAD rather than mean and sd:

```
center = median(x_1..x_n)
scale  = 1.4826 × MAD(x)          # consistent with sd under normality
z      = (x_t − center) / scale
```

With n < 6, MAD is unstable; blend toward the prior scale (below).

### Prior shrinkage (cold start)
The system must be useful on month 1. Start from café-sector priors and let observed history displace them.

```
prior:   center₀, scale₀, pseudo-count n₀ = 3
center* = (n₀·center₀ + n·median(x)) / (n₀ + n)
scale*  = sqrt((n₀·scale₀² + n·(1.4826·MAD)²) / (n₀ + n))
prior_weight = n₀ / (n₀ + n)
```

### Seed priors
Ratios to revenue unless stated. Centers drawn from published independent-café benchmarks (Bellwether, ATO small-business benchmarks, Zest, EFM); scales set wide enough that a healthy café sits within ±1σ and a warning-zone café sits at roughly +2σ.

| Metric | center₀ | scale₀ | Warning zone per benchmarks |
|---|---|---|---|
| gross margin | 68% | 5pp | < 60% |
| COGS / revenue | 31% | 5pp | > 40% |
| labor / revenue | 30% | 5pp | > 40% |
| rent / revenue | 11% | 3pp | > 15 to 18% |
| utilities / revenue | 3% | 1pp | |
| other opex / revenue | 7% | 2.5pp | |
| net margin | 12% | 5pp | < 5% |
| milk / COGS | 18% | 4pp | |
| coffee beans / COGS | 30% | 6pp | |
| food / COGS | 35% | 8pp | |
| packaging / COGS | 8% | 3pp | |
| espresso-drink unit margin | 78% | 6pp | |
| iced / cold-brew unit margin | 68% | 7pp | |
| food unit margin | 55% | 10pp | |
| month-over-month AOV drift | 0% | 3% | |
| month-over-month volume drift | 0% | 8% | |
| electricity seasonal amplitude | ±15% | 8pp | |

Where the source benchmarks disagree (labor 25 to 35% in some, 30 to 35% in others), the center is the overlap and the scale absorbs the disagreement.

### Confidence gating

| Observed periods n | prior_weight | Confidence cap | Narrative tag |
|---|---|---|---|
| 0 to 2 | ≥ 0.6 | 0.60 | `prior_dominant` |
| 3 to 5 | 0.38 to 0.5 | 0.80 | `prior_assisted` |
| ≥ 6 | ≤ 0.33 | 1.00 | none |

`prior_dominant` findings say so in the text: *"Measured against café-sector norms rather than your own history, which I don't yet have."* Priors are seeds, never conclusions.

### Anomaly and persistence
Flag |z| > 2. Persistence = consecutive periods with |z| > 1.5. Direction-aware: a cost below range is not an anomaly for ranking purposes but is logged (it may be a missing invoice, which §14 checks).

---

## 13. Materiality ranking

The brief's formula (`dollar_impact × abnormality × persistence × business_relevance`) is conceptually right and numerically dangerous if implemented literally. Four ways a raw product breaks: a near-zero factor zeroes a real problem (a $5k expected seasonal hike has abnormality ≈ 0); persistence penalizes new problems, which is backwards for a proactive agent; unbounded dollars swamp the bounded factors so the score degenerates to sort-by-dollars; and raw products are not comparable across periods, which undermines the multi-period story. The implementation below keeps the brief's four ideas and fixes the arithmetic.

### Gate, then score

```
GATE:    |dollar_impact| ≥ max($150, 0.25% of revenue)   else not ranked at all

D  = log1p(|dollar_impact| / gate_floor) / log1p(max_impact / gate_floor)     ∈ [0, 1]
A  = clip((|z| − 1) / 3, 0.15, 1)                                             ∈ [0.15, 1]
P  = 1 + 0.15 · min(persistence − 1, 3)                                       ∈ [1, 1.45]  boost only
C  = controllability prior per leaf                                           ∈ [0.1, 0.9]
H  = 0.7 + 0.3 · HHI                                                          ∈ [0.7, 1]   concentration boost

materiality = 100 · D^0.5 · A^0.3 · P · C · H     then rescaled so the period's top item = 100
```

Design notes:
- The gate removes noise before anything is scored; nothing below it has to be explained away in front of a judge.
- Log-scaled dollars keep D bounded so abnormality and controllability actually move the ranking instead of being decoration.
- A has a floor of 0.15, never 0. An expected-but-large hit still ranks; it ranks below an unexpected one of the same size.
- P is a boost with a floor of 1. A brand-new $3k problem ranks on its dollars in month 1 and ranks higher if it is still there in month 3.
- H rewards concentration because "one supplier is 90% of this" is more actionable than "200 transactions each moved a little", and this is the track's stated preference.
- Exponents 0.5 and 0.3 are the relative weight of dollars versus abnormality. They are declared constants in `materiality.py` with a comment, so the answer to "why did ingredients beat electricity" is a formula, not vibes.
- Rescaling to top = 100 makes scores comparable across periods: "this month's top issue is 100 and last month's was 100" is by construction, so the dashboard also shows the raw pre-rescale score for absolute comparison.

### Persistence is matched at attribution level, not category level
"Ingredients flagged two months running" is only persistence if it is the same driver. Milk up in July from a supplier hike and milk up in August from higher volume are two problems, not one recurring problem. Persistence is counted along `recurs_from` edges between `attribution` nodes with the same leaf and, where concentration exists, the same top contributor. A category-level match is never used.

### Controllability priors
price 0.9, items_per_order 0.7, mix 0.6, usage_efficiency 0.7, unit_cost 0.5, labor 0.7, conversion 0.6, traffic 0.3, electricity 0.4, other_opex 0.5, rent 0.1. Declared per business model in `graph_def.py`; the café values are the only ones shipped, which is a stated limitation (§31, item 1).

| Leaf | $ | z | persist | HHI | control | score |
|---|---|---|---|---|---|---|
| mix | −1,420 | 2.4 | 1 | 0.51 | 0.6 | 100 |
| unit_cost milk | −930 | 3.1 | 2 | 0.82 | 0.5 | 91 |
| electricity | −760 | 2.9 | 3 | n/a | 0.4 | 58 |
| conversion | −570 | 1.8 | 1 | n/a | 0.6 | 44 |

Electricity is the most abnormal and the most persistent. It ranks third because dollars, controllability and concentration dominate. The narrative must say this explicitly; that judgment is what separates an analyst from an anomaly detector.

---

## 13b. Relationship rules (the proactive layer)

Attribution explains a variance that has already been detected. This layer detects a different kind of problem: a **broken expected relationship** between two metrics that may each look fine on their own. It runs every period before the investigation agent and is what lets the system speak first.

Each rule is deterministic Python, declares its trigger, the dollars at stake, and where the investigation agent should drill. No LLM in the trigger.

| Rule | Trigger | Dollars at stake | Drill into |
|---|---|---|---|
| `traffic_revenue_gap` | traffic Δ% − revenue Δ% > 3pp | (traffic Δ% − revenue Δ%) × revenue | conversion, items_per_order, AOV by hour |
| `revenue_profit_divergence` | revenue Δ% > 0 and contribution Δ% < 0 | contribution Δ$ | mix, unit costs, usage |
| `margin_compression` | revenue Δ% > 0 and contribution margin Δpp < −1.5 | Δpp × revenue | mix, price, unit_cost |
| `volume_without_cost_scaling` | orders Δ% > 5 and variable cost Δ% < 1 | flag, not $ | data quality: costs possibly lagging (§6 basis) |
| `cost_without_volume` | any variable input qty Δ% > orders Δ% + 8pp | excess qty × unit cost | usage_efficiency, waste, theft |
| `recurring_revenue_erosion` | recurring-customer revenue share ↓ ≥ 3pp while total flat | share Δ × revenue | retention (if customer ids exist) |
| `concentration_creep` | top-3 counterparty share of any leaf ↑ ≥ 10pp over 3 periods | share × leaf spend | supplier dependency risk |
| `price_no_volume_response` | price Δ% ≥ 3 and volume Δ% ≥ 0 | flag | elasticity estimate update (§15) |
| `fixed_cost_step` | any fixed leaf step-changes ≥ 8% with no prior drift | Δ$ | contract change, one-off |
| `seasonal_break` | metric departs from its learned seasonal pattern (§18) by > 2σ | Δ$ vs seasonal expectation | pattern validity, external |

Rules emit `relationship_flag` nodes. They are ranked by the §13 formula like any variance (dollars at stake as the impact), so a rule firing on a $90 gap does not lead the briefing. The investigation agent treats a relationship flag as a leaf with a pre-supplied drill plan.

Ten rules is the right number for the hackathon. The `traffic_revenue_gap` rule fires on the demo scenario and is the reason the briefing can say "you were 15% busier but only 11% up in sales, so roughly one in thirty visitors who would have bought last month did not this month" before anyone asks.

---

## 14. Leakage and overcharging detection

Each rule runs against the counterparty's or SKU's own history with the §12 shrinkage. Every flag carries `gap_dollars`, the evidence rows, and a mandatory counter-explanation.

| Rule | Detection | Counter-explanation to check |
|---|---|---|
| Duplicate payment | same counterparty, amount ±1%, ≤ 3 days, no distinct invoice ref | legitimate split delivery |
| Unit-cost outlier | supplier unit cost z > 2.5 vs own history | product change, smaller order tier |
| Silent price creep | unit cost +≥1.5% per period for ≥3 periods, no market corroboration (§19) | contract escalator clause |
| Shrinkflation | unit price flat, delivered qty ↓, effective unit cost ↑ | pack-size change disclosed |
| Quantity mismatch | inputs purchased > sales-implied usage × (1 + waste band) | stock build-up, spoilage event |
| Round-number clustering | share of round-hundred invoices from one counterparty z > 2 | genuine flat-rate contract |
| Off-cycle charge | billing outside established cadence (median interval ± 2 MAD) | annual fee, one-off order |
| New-vendor spike | new counterparty > 3% of monthly spend in first period | planned switch |
| Ghost recurring | recurring charge continues after linked activity stops | contract still valid |
| Missing expected charge | recurring counterparty absent in period | paid late, will appear next period |

Market corroboration for price-creep and unit-cost rules is obtained through §19 with the `market_conditions` template. Where the market moved less than the supplier, the gap is quantified:

```
WORTH VERIFYING                                  (n_lk_02)
Nordic Dairy Co unit cost rose 22% (z = 3.1 vs their own 11-month history).
Regional dairy wholesale conditions searched: increases of roughly 6 to 8%.
Unexplained gap ≈ 14%, about $610 this month, $7,300 annualized if it holds.
Before raising it with them: your order volume fell 30% in July. Check whether
that moved you off a volume tier in your contract.
```

The agent never uses the words fraud, scam, cheat or overcharge in output. It states the gap and the counter-explanation and hands the judgment to the owner. This is correct epistemics and the only defensible posture.

---

## 15. Sensitivity engine

Forward-looking. Perturb each controllable leaf through `profit_fn` and report Δcontribution per unit of intervention. The basis is contribution (§7), never gross profit: a price move that shifts volume also shifts variable labor, card fees and equipment load, and a gross-margin calculation silently books those as zero.

```python
for leaf in controllable:
    for delta in [-0.10, -0.05, +0.05, +0.10]:
        state = curr.copy(); state[leaf] *= (1 + delta)
        if leaf == "price":
            state["volume"] *= (1 + delta * elasticity[leaf])   # see below
        sim[leaf][delta] = profit_fn(state) - profit_fn(curr)
```

### Elasticity
A price recommendation with an unstated elasticity assumption is not analysis. Default own-price elasticity for café drinks −0.4 (inelastic, consistent with habitual purchase), reported as an explicit assumption and swept across [−0.2, −0.4, −0.8]. If the history contains ≥2 prior price changes on a product, estimate elasticity from them (log-log on ΔQ vs ΔP, controlling for traffic) and report the fitted value with its n.

Output includes confidence, computed from assumption sensitivity: if the ranking of interventions is stable across the elasticity sweep, confidence is high.

```
Intervention                          Δprofit/mo   Elasticity sweep    Confidence
iced-drink prices +5%                    +$2,900    +$2,400 to +$3,200    0.72
milk unit cost −8% (to prior level)      +$1,100    n/a                   0.55
milk usage −5% (portioning)                +$460    n/a                   0.70
electricity −10%                           +$240    n/a                   0.80
```

Enables: *"Electricity rose most in percentage terms, but pricing carries roughly 12× the financial leverage under the modeled assumptions."*

The narrative is required to state the assumption in the same sentence as the number: "assuming volume holds" or "assuming about 2% of iced-drink volume is lost". A leverage claim without its elasticity is not permitted through the validator (§21).

---

## 16. Target directives

Each controllable leaf receives a directive for next period, rendered as the indicator in the UI.

```json
{
  "driver": "unit_cost.milk",
  "node_id": "n_dir_07",
  "current": 4.82, "unit": "USD/L",
  "normal_range": [3.90, 4.25],
  "direction": "down",
  "target": 4.20,
  "gap_dollars_month": 1100,
  "controllability": 0.5,
  "indicator": "red_down",
  "justifies": ["n_7c1e04", "n_lk_02"],
  "review_period": "2026-09"
}
```

| Indicator | Condition |
|---|---|
| red down | above range, gap ≥ $250/mo, reduce |
| red up | below range in a higher-is-better metric (traffic, AOV, margin) |
| amber | inside range but same-direction drift ≥ 2 periods |
| grey | inside range |
| green check | flagged last period, now inside range |

No indicator is set by LLM judgment. All come from `normal_range` (§12) and sensitivity (§15).

### Directive scoring (next period)
For every directive issued in period t, at t+1 record: moved toward target (bool), fraction of gap closed, realized Δprofit on that leaf vs modeled. Aggregate into `directive_hit_rate` and `impact_calibration` (§24). This is the closest thing the system has to ground truth about itself.

---

## 17. Investigation agent: protocol

The LLM receives the ranked leaf list with attribution, concentration, anomaly, leakage, sensitivity, transaction evidence samples, and the carry-forward object (§18). It processes leaves in materiality order until the cumulative explained share of the top variance exceeds 85% or the per-run budget (6 leaves, 12 tool calls, 4 Tavily calls) is exhausted.

Per leaf:

```
1. LOAD prior state       recurs_from → last period's hypotheses and verdicts on this leaf
2. CLASSIFY               pick hypothesis classes from the template set (§17.1); local model
3. INSTANTIATE            fill each template with this period's concentration entities
4. PLAN evidence          for each hypothesis: which internal query or external search would
                          discriminate it from the others (not merely be consistent with it)
5. GATHER internal        run the planned DuckDB queries; write evidence nodes
6. GATHER external        only if internal evidence leaves ≥2 hypotheses live and a concrete
                          external fact would separate them; §19
7. UPDATE beliefs         §17.3; write belief_update nodes
8. VERDICT                §17.4; write verdict node
9. QUESTION               if the leading hypothesis is unresolved and owner knowledge would
                          resolve it, emit a question candidate for §20
10. NEXT leaf
```

### 17.1 Hypothesis templates

Templates are keyed by leaf and pre-declare what evidence discriminates them. The LLM chooses and instantiates; it does not free-associate.

| Leaf | Class | Claim template | Discriminating internal evidence | External |
|---|---|---|---|---|
| unit_cost[i] | `market_inflation` | input {i} rose with the broader market | all suppliers of {i} rose similarly | market_conditions |
| unit_cost[i] | `supplier_specific` | {supplier} raised price beyond market | only {supplier} rose; others flat | market_conditions (negative corroboration) |
| unit_cost[i] | `order_tier` | order size fell, lost volume discount | order qty ↓ same period; unit cost step-change not gradual | none |
| unit_cost[i] | `product_switch` | switched to premium variant | SKU / description changed | none |
| mix | `seasonal` | iced share rises in warm months | same pattern prior year if available; cooling degree days | weather |
| mix | `menu_change` | new item cannibalized high-margin items | new SKU appears; loser's decline ≈ winner's gain | none |
| mix | `promo` | discount drove low-margin volume | avg price of winner ↓ | none |
| volume | `traffic` | fewer / more customers | traffic metric if present; orders count | local_events, weather |
| conversion | `checkout_friction` | queue / POS / staffing at peak reduced completed orders | orders per traffic ↓ concentrated in peak hour bucket; hours metric | none |
| conversion | `browse_traffic` | traffic rose with non-buying visitors (event, weather shelter) | traffic ↑ evenly, orders flat, no peak concentration | local_events, weather |
| volume | `conversion` | same traffic, fewer orders | traffic flat, orders ↓ | none |
| volume | `competitor` | new competitor nearby | gradual decline, no internal cause | competitor_prices, local_events |
| electricity | `weather` | heat drove cooling load | cooling degree days ↑ | weather |
| electricity | `equipment` | equipment inefficiency or fault | elevation persists after weather normalizes; kWh/order ↑ | none |
| electricity | `tariff` | rate change | kWh flat, $ ↑ | market_conditions |
| labor | `hours` | more hours scheduled | hours metric; opening hours | none |
| labor | `rate` | wage rate change | hours flat, $ ↑ | market_conditions (minimum wage) |
| usage_efficiency | `waste` | portioning / spoilage | input qty per drink ↑ | none |

Each template carries a prior belief `p₀` (e.g. `market_inflation` 0.4, `supplier_specific` 0.3, `order_tier` 0.2, `product_switch` 0.1 for unit_cost) so the belief update has a starting point that is not uniform.

### 17.2 Evidence planning rule
An evidence item is only worth gathering if it changes the posterior of at least one live hypothesis by ≥ 0.1 in expectation. Evidence that is consistent with every live hypothesis is not gathered; it is noise dressed as diligence. The plan is written as a `payload` on the hypothesis node so PRISM can show the reasoning.

### 17.3 Belief update
Not full Bayes over free text. A structured approximation the LLM must fill:

```json
{
  "hypothesis": "h_014",
  "evidence": "n_ev_31",
  "support": "strong_for | weak_for | neutral | weak_against | strong_against",
  "likelihood_ratio": 4.0,
  "note": "all three dairy suppliers rose 6 to 9%; only Nordic rose 22%"
}
```

Likelihood ratios are constrained to {8, 4, 1.5, 1, 0.67, 0.25, 0.125} mapped from the support labels, so the LLM picks a category, not a number. Posterior odds = prior odds × Π LR. Temporal-correlation-only evidence is capped at `weak_for` (LR 1.5) by rule, regardless of what the LLM says. This cap is the single most important reliability control in the system and is what the Observe → Improve → Prove demo (§25) turns on.

### 17.4 Verdict rules

| Verdict | Condition |
|---|---|
| `supported` | posterior ≥ 0.7 AND ≥1 supporting evidence of tier ≤ 2 that is not temporal-only AND no strong_against |
| `weakening` | previously supported, this period's evidence moved posterior down by ≥ 0.2 |
| `rejected` | posterior ≤ 0.15 or any strong_against from tier-1 internal evidence |
| `unresolved` | otherwise; must produce a question candidate or state what evidence is missing |

`supported` never means proven; the narrative uses "the evidence points to" and states the posterior.

### 17.5 Model routing

| Step | Model | Why |
|---|---|---|
| classify templates | Ornith 9B local | cheap, constrained choice |
| instantiate, plan evidence | cloud | needs judgment |
| belief update labels | cloud | needs judgment, constrained output |
| verdict | rule-based | no model |
| narrative, questions, revision | cloud | language quality |

---

## 18. Business memory and carry-forward

**Numbers are never summarized.** All periods stay in DuckDB and are queried in full. Compressing figures into prose and reasoning over the prose is how an agent starts inventing numbers, and it violates §21's validator by construction.

**Only judgments carry forward**, in a fixed-schema object that is revised, not appended.

```json
{
  "version": 12,
  "open_hypotheses": [
    {"id": "h_014", "leaf": "electricity", "class": "weather",
     "posterior": 0.35, "trend": "falling", "first_seen": "2026-07",
     "periods_elevated": 3, "evidence": ["n_ev_31", "n_ev_47"]}
  ],
  "closed_hypotheses": [
    {"id": "h_009", "leaf": "other_opex", "class": "one_off",
     "verdict": "supported", "closed": "2026-07"}
  ],
  "directives": [
    {"id": "n_dir_07", "leaf": "unit_cost.milk", "issued": "2026-08",
     "target": 4.20, "expected_dollars": 1100,
     "acted": null, "observed_dollars": null}
  ],
  "owner_answers": [
    {"q": "q_003", "asked": "2026-08", "text": "switched to Nordic in July for delivery reliability",
     "encoded": {"leaf": "unit_cost.milk", "class": "product_switch", "support": "strong_for"}}
  ],
  "learned_patterns": [
    {"pattern": "iced share rises Jun to Sep", "support_periods": 4, "confidence": 0.7},
    {"pattern": "electricity lags cooling degree days ~2 weeks", "support_periods": 2, "confidence": 0.4}
  ],
  "baseline_version": "posterior_2026-08"
}
```

Caps: 15 open hypotheses, 20 directives, 30 answers, 10 patterns. Eviction score `staleness × (1 − materiality)`. Twelve periods in, this object is the same size as after two. That, not summarization, is what bounds the context.

Owner answers are encoded into the same `support` vocabulary as evidence so they enter the belief update like any other evidence node, with `tier 1` (§19) because the owner is the authority on their own operations.

### Owner feedback on findings
Every finding carries three buttons in the dashboard and one voice prompt: **right**, **wrong**, **incomplete**. Feedback is stored per finding with the hypothesis class and leaf, and used in two ways, both deterministic:

1. **Template prior adjustment.** Each `wrong` on a hypothesis class multiplies that class's `p₀` (§17.1) by 0.8 for this business; each `right` by 1.15, capped at [0.05, 0.8]. After a few periods the café's own history of what explanations turned out to be true shapes which hypotheses the agent reaches for first.
2. **Materiality weight adjustment.** `incomplete` on a finding whose leaf was ranked below the gate nudges that leaf's controllability prior up by 0.05, because the owner is telling the system it cares about that line.

Feedback is `tier 1` evidence and appears in the graph as `feedback` nodes with `answers` edges to the finding. The dashboard reports the running tally per class ("supplier-specific explanations: 4 right, 1 wrong") so the claim "the agent learns what this business cares about" is a number, not a slogan.

```json
"feedback": [
  {"finding": "f_001", "period": "2026-08", "verdict": "right",
   "class": "supplier_specific", "leaf": "unit_cost.milk"},
  {"finding": "f_003", "period": "2026-08", "verdict": "incomplete",
   "class": null, "leaf": "conversion", "note": "we had a POS outage for 2 days"}
]
```

### Analog retrieval
Before the investigation agent runs on a leaf, the engine searches closed hypotheses for the same leaf with a similar attribution signature (same sign, top contributor overlap, |z| within 1). A match is injected as a tier-1 `analog` evidence node with LR 1.5 (never higher, because "it happened before" is not proof it is happening again), and the narrative gets to say: *"This resembles March, when the same supplier's increase turned out to be a lost volume tier."* That sentence is what the track means by intuition over time, and it costs one DuckDB query.

---

## 19. External research (Tavily)

### Trigger rule
Search only when (a) a leaf is material, (b) ≥2 hypotheses remain live after internal evidence, and (c) a concrete external fact would separate them. Never search to "understand the business" or "find causes". Budget 4 calls per run.

### Query templates

| Template | Fires for | Query shape | Params |
|---|---|---|---|
| `market_conditions` | unit_cost, labor rate, electricity tariff | "{input} wholesale price {region} {month year}" | topic=finance or news, time_range=month, search_depth=advanced, max_results=5 |
| `weather` | electricity, mix, volume | "{city} weather {month year} temperature" | topic=general, start_date/end_date = period bounds |
| `local_events` | volume | "{city} {neighbourhood} events road closure {month year}" | topic=news, start/end = period bounds |
| `competitor_prices` | volume, price | "{city} café latte price {year}" | topic=general, search_depth=advanced, include_domains=[review and menu sites] |
| `regulatory` | labor rate | "{jurisdiction} minimum wage change {year}" | topic=news, time_range=year |

The period's date bounds go into `start_date` / `end_date` so evidence is temporally scoped to the variance, and `include_answer` is off so the agent reads sources rather than a synthesized answer it cannot audit.

### Source tiers

| Tier | Source | Max LR contribution |
|---|---|---|
| 1 | owner answer; internal transaction data | 8 |
| 2 | statistical agency, commodity exchange, central bank, weather service, supplier's published price list | 8 |
| 3 | trade press, established news | 4 |
| 4 | blogs, forums, aggregators, AI summaries | 1.5 |

A `supported` verdict requires tier ≤ 2 evidence. Tier 4 alone can never move a hypothesis past `unresolved`.

### Corroboration extraction
The cloud model reads each result and emits a structured extract:

```json
{"source_url": "...", "tier": 3, "published": "2026-08-14",
 "claim": "regional dairy wholesale prices rose 6 to 8% July to August",
 "quantity": {"metric": "dairy_wholesale_price_change", "value": 0.07, "range": [0.06, 0.08]},
 "relevance": "direct | adjacent | weak",
 "support_for": {"h_021": "weak_for", "h_022": "strong_for"}}
```

Where a quantity is extracted, the engine (not the LLM) computes the corroborated share and the unexplained gap: `gap = supplier_change − market_change`, and that gap becomes the number in §14's output.

### Failure handling
No results, or only tier 4: hypothesis stays `unresolved`, the narrative says external evidence was sought and not found, and a question candidate is generated. The agent never fills the gap with training-data priors about commodity markets.

---

## 20. Question engine

The highest-value information in a small business is in the owner's head and in no CSV. Asking is a feature.

### Selection
For each `unresolved` or `weakening` hypothesis with owner-resolvable class (order_tier, product_switch, menu_change, promo, hours, equipment, contract terms):

```
VOI = unexplained_dollars × p_resolves × future_relevance
p_resolves      = 0.8 for operational facts, 0.4 for judgment questions
future_relevance = 1.0 if the leaf is recurring, 0.5 if one-off
```

Top 3 by VOI, minimum VOI $150. Each question names the dollars it would resolve and offers a closed set of answers where possible so the reply encodes cleanly into §18.

```
I can account for $3,900 of the $4,820 decline. To close the rest:

1. Did your milk supplier or contract terms change around July?
   (a) switched supplier  (b) same supplier, new terms  (c) no change  (d) not sure
   Would resolve about $610 of unexplained ingredient cost.

2. Were opening hours or staffing extended in August?
   (a) yes, planned  (b) yes, unplanned cover  (c) no
   Would resolve about $330 of labor variance.
```

### Rules
- Never ask what is derivable from the data
- Maximum 3 per period
- Unanswered questions decay after 2 periods; the finding is then marked permanently `unresolved`, never quietly guessed
- Answers arrive via dashboard or voice (§22 post-call webhook), are encoded to the `support` vocabulary, and persist in `owner_answers`

---

## 21. Structured output, validation, and dashboard

### Structured findings
Produced before any natural language. Dashboard and voice consume only this.

```json
{
  "period": "2026-08", "run_id": "r_012", "status": "complete",
  "reconciliation": "passed", "confidence_regime": "prior_assisted",
  "headline": {"metric": "operating_profit", "change": -4820, "change_pct": -7.1,
               "context": "revenue +11.2%, traffic +15%", "node": "n_0f3a91"},
  "findings": [
    {"id": "f_001", "severity": "high",
     "title": "Profit fell despite revenue growth",
     "attribution": ["n_7c1e04", "n_7c1e05", "n_7c1e06", "n_7c1e07"],
     "concentration": ["n_cn_02", "n_cn_03"],
     "hypotheses": [{"id": "h_021", "verdict": "supported", "posterior": 0.82},
                    {"id": "h_022", "verdict": "unresolved", "posterior": 0.45}],
     "evidence": ["n_ev_31", "n_ev_47"],
     "simulations": ["n_sim_03", "n_sim_04"],
     "directives": ["n_dir_07", "n_dir_08"],
     "confidence": 0.79}
  ],
  "verify": ["n_lk_02"],
  "improved": ["n_var_11"],
  "questions": ["q_007", "q_008"],
  "revisions": [{"old": "n_v_009", "new": "n_v_019",
                 "summary": "electricity: weather downgraded from supported to weakening"}],
  "next_period_watch": ["electricity", "unit_cost.milk"]
}
```

### Output validator
Runs on every narrative and every voice utterance before delivery. Extracts numeric tokens (currency, percent, counts), normalizes, and matches each against the value set of nodes referenced by the findings, with tolerance for rounding ($4,820 ↔ "about $4,800"). Any unmatched number fails the run and PRISM records `unsourced_figure`. This is enforcement, not prompting.

### Dashboard views

**Period report.** Four blocks: what went wrong, what improved, worth verifying, next period targets. Each line links to its node.

**Anomaly overlay.** The P&L and product tables render normally; flagged cells get a colored marker sized by materiality (not by percentage), with z, persistence and dollar gap on hover. A toggle switches the coloring basis between own-history and sector-prior so the owner can see how much the judgment depends on priors.

**Directive strip.** One indicator per controllable leaf (§16). Click → the attribution and simulation nodes that justify it.

**Graph view.** The RCG as a DAG, period on the x-axis, type on the y-axis. Color by provenance: deterministic, inferred, retrieved. Superseded nodes greyed with a link to their replacement. Click any node for formula, inputs, value, confidence. Filter by leaf to see one driver's story across periods. This view is the differentiator: it shows the boundary between computed and reasoned, and it shows the agent changing its mind.

**Drill-through.** Any number on any surface walks up `derives_from` to raw rows.

**Question panel.** Open questions with answer buttons; answers post to the memory endpoint.

---

## 22. ElevenLabs voice agent

### Agent configuration
One agent on the Agents Platform. System prompt establishes the role (financial analyst for {business_name}), the rule that every figure comes from tool results, and the register (plain, short sentences, no jargon). `first_message` is templated from the structured findings via dynamic variables so the proactive briefing is spoken without a user turn.

Dynamic variables set at conversation start: `business_name`, `period`, `headline_text`, `finding_count`, `top_finding_title`, `run_id`.

### Server tools (webhooks into the backend)

| Tool | Returns |
|---|---|
| `get_briefing(run_id)` | headline + top finding titles, pre-rendered text |
| `get_finding(run_id, finding_id)` | attribution lines, concentration, verdicts, pre-rendered |
| `get_recommendations(run_id)` | ranked simulations with assumptions, pre-rendered |
| `get_verify_items(run_id)` | leakage flags with counter-explanations, pre-rendered |
| `get_questions(run_id)` | open questions with option sets |
| `record_answer(run_id, question_id, option)` | ack; writes to memory |
| `get_revisions(run_id)` | what changed since last period |

Every tool returns pre-rendered sentences generated by the backend narrative step and already validated (§21). The voice model's job is to select and sequence them, not to compose figures. Tool descriptions say so explicitly.

### Guardrails
Content guardrail with retry action: if the agent's utterance contains a numeric token not present in the last tool results, retry with feedback "restate using only figures returned by tools". Up to 3 attempts, then fall back to reading the tool text verbatim. `end_call` built-in tool enabled.

### Post-call webhook
Transcript posted to the backend. Owner answers captured through `record_answer` are already stored; the transcript is additionally scanned for unstructured operational facts ("we started opening Sundays") and those become question candidates for confirmation next period rather than being encoded directly.

### Conversation flow

```
Agent (proactive, no user turn):
  "I've analyzed August. Three things worth your attention. The most important:
   the café was 15% busier and revenue rose 11%, but operating profit fell about
   $4,800. Want me to walk through what caused it?"
Owner: "Yes."
Agent → get_finding(f_001):
  "Two things did most of it. Ingredient costs, mainly milk and beans, took about
   $2,300. A shift toward iced drinks, which carry lower margins, took about $1,400.
   Electricity also rose 26%, but that's only about $760."
Owner: "What should I do first?"
Agent → get_recommendations:
  "Pricing has the most leverage. A 5% increase on your top iced drinks models to
   roughly $2,900 a month, assuming volume holds. That's about twelve times what
   fixing electricity would return."
Owner: "Anything I should check?"
Agent → get_verify_items:
  "One thing. Your dairy supplier's price rose 22%, but regional dairy costs rose
   about 7%. That's a gap of roughly $610 a month. Your order size also dropped in
   July, so check whether you fell off a volume tier before raising it with them."
Agent → get_questions:
  "Can I ask you one thing? Did your milk supplier or contract change around July?"
Owner: "We switched to Nordic in July."
Agent → record_answer(q_007, "a")
  "Noted. That changes the picture on milk; I'll factor it in next month."
```

---

## 23. PRISM instrumentation

Trace tree mirrors RCG writes. Every span carries the node ids it produced so a PRISM span and a graph subgraph are the same object.

```
analysis_run {run_id, period, agent_version}
├── ingest {rows, files}
├── reconcile {checks[], status}
├── calculate_metrics {node_count}
├── update_baselines {prior_weight, n}
├── detect_variances {material_count}
├── decompose_shapley {leaves, sum_check}
├── concentration {per_leaf}
├── rank_materiality {ranking[]}
├── leakage_scan {flags[]}
├── sensitivity {interventions[], elasticity_sweep}
├── investigate[leaf] ×N
│   ├── load_prior_state
│   ├── classify_templates {model=local}
│   ├── instantiate_hypotheses {h_ids[]}
│   ├── plan_evidence {plan[]}
│   ├── internal_evidence {queries[], nodes[]}
│   ├── tavily_search {template, query, params, results, tiers[]}   (0..1)
│   ├── belief_update {LRs[], temporal_cap_applied}
│   ├── verdict {rule_fired}
│   └── question_candidate
├── select_questions {voi[]}
├── simulate_recommendations
├── compute_directives
├── score_prior_directives {hit_rate, calibration}
├── generate_findings
├── validate_output {unsourced_figures: 0}
├── generate_narrative
└── voice_delivery {tool_calls[], guardrail_retries}
```

Captured per span: inputs (hashes for large), outputs, latency, model, token counts, failures with the failure-taxonomy label (§24).

---

## 24. PRISM evaluation

### Metrics

| Metric | Definition | Target |
|---|---|---|
| `primary_driver_accuracy` | top-ranked leaf equals scenario ground truth | ≥ 0.9 across scenario set |
| `attribution_error` | mean \|φ_i − φ_i*\| / \|Δprofit\| over leaves, vs generator truth | ≤ 0.05 |
| `sum_check_pass` | invariant 3 holds | 1.0 |
| `false_causal_rate` | `supported` verdicts whose ground truth is "not a driver" | 0 |
| `unsupported_conclusion_rate` | `supported` with no tier ≤ 2 evidence | 0 |
| `unsourced_figure_rate` | validator failures per run | 0 |
| `temporal_cap_violations` | LR > 1.5 on temporal-only evidence | 0 |
| `leakage_precision / recall` | vs injected overcharge events | P ≥ 0.8, R ≥ 0.7 |
| `question_relevance` | fraction of questions whose answer changes a verdict in the generator's answer set | ≥ 0.7 |
| `revision_rate` | contradicted prior verdicts that produce a revision node | 1.0 |
| `directive_hit_rate` | directives where the leaf moved toward target next period (backtest) | reported |
| `impact_calibration` | modeled vs realized Δprofit, mean ratio | reported |
| `latency_p50 / p95` | full run | ≤ 90s / 180s |
| `tavily_calls_per_run` | | ≤ 4 |

### Failure taxonomy
Every failed assertion gets one label: `reconcile_block`, `sum_mismatch`, `residual_mix`, `wrong_primary`, `percent_ranking`, `causal_from_correlation`, `unsourced_figure`, `tier4_supported`, `question_derivable`, `no_revision`, `voice_new_figure`, `budget_exceeded`.

### Regression scenarios

| Id | Scenario | Ground truth | Pass condition |
|---|---|---|---|
| A | ingredient inflation | all input unit costs +15 to 20%, market corroborates | primary = unit_cost; `market_inflation` supported |
| B | product mix | iced share +8pp, prices flat, revenue ↑ profit ↓ | primary = mix; mix not residual |
| C | traffic | traffic −18%, everything else flat | primary = volume; `traffic` supported, `competitor` not supported |
| D | false weather | rain in weak month, decline caused by traffic on dry days too | no `supported` weather verdict; temporal cap fires |
| E | distracting anomaly | electricity +30% / $200, ingredients +10% / $4,000 | primary = unit_cost; narrative states the leverage comparison |
| F | supplier overcharge | one supplier +22%, market +7% | leakage flag with gap ≈ 15%; no accusatory language |
| G | cold start | month 1 only | run completes; `prior_dominant`; confidence ≤ 0.6 |
| H | slow drift | milk +4%/mo × 6 | quarterly level-drift flag; monthly runs do not flag |
| I | revision | Jul weather-consistent, Sep weather normal, electricity still high | Sep produces `revision` node; `equipment` becomes leading |
| J | order tier | order qty −30%, unit cost step +12%, market flat | `order_tier` leads; question asked about contract |
| K | duplicate invoice | same supplier, same amount, 2 days apart | reconciliation WARN + leakage flag |
| L | reconciliation block | summary revenue off by 5% | ANALYSIS_BLOCKED, no findings emitted |
| M | voice figure injection | prompt the voice agent to state a made-up number | guardrail retry fires; validator rejects |
| N | traffic-revenue gap | traffic +15%, orders +11%, everything else flat | `traffic_revenue_gap` fires; conversion leaf is negative; narrative mentions it |
| O | feedback learning | owner marks `supplier_specific` wrong twice | class p₀ falls; next period's first hypothesis on unit_cost is `market_inflation` |
| P | cash / accrual window | POS cash export vs accrual summary, 3 straddling invoices | reconciles after cutoff adjustment; rows tagged `basis_adjusted` |

Harness: `pytest -m regression` runs every scenario against the generator (§26), asserts pass conditions, uploads traces to PRISM tagged with `agent_version`. PRISM comparison view is agent_version × scenario × metric.

---

## 25. Observe → Improve → Prove

Run live during the presentation.

**Observe.** Agent v0.2 on scenario D concludes: "Rain caused the sales decline." Open the PRISM trace: `belief_update` shows the weather hypothesis received `strong_for` (LR 8) from a single tier-3 weather article whose only content is that it rained that month. No evidence discriminated weather from traffic.

**Improve.** Two changes, both visible in the diff: (1) temporal-only evidence capped at `weak_for` (§17.3); (2) `supported` requires tier ≤ 2 non-temporal evidence (§17.4). Bump to v0.3.

**Prove.** Rerun D. Output: "Rain coincided with the decline, but dry-day traffic also fell 14%, so weather does not sufficiently explain it. Traffic is the leading driver; I could not determine why from the data. Did anything change nearby in August?" Side-by-side in PRISM: v0.2 `false_causal_rate` 1.0 → v0.3 0.0, with the full scenario matrix showing no regressions elsewhere.

Then one more: rerun scenario I on both versions to show v0.3 also revises its own prior verdict, which v0.2 never did.

---

## 26. Synthetic data generator

Parameterized so every regression scenario is one config file. Generates transaction-level CSV, monthly summary CSV, optional operational metrics, and a `truth.json` with the injected effects and the leaf-level attribution the generator can compute exactly (because it knows its own perturbations).

```yaml
scenario: B_product_mix
months: 6
base:
  daily_orders: {mean: 210, sd: 25}
  products:
    espresso:   {price: 3.20, unit_cost: 0.45, share: 0.18}
    latte:      {price: 5.00, unit_cost: 1.20, share: 0.26}
    iced_latte: {price: 5.50, unit_cost: 1.85, share: 0.16}
    cold_brew:  {price: 4.80, unit_cost: 1.60, share: 0.09}
    drip:       {price: 2.80, unit_cost: 0.35, share: 0.21}
    pastry:     {price: 3.75, unit_cost: 1.70, share: 0.10}
  inputs:
    milk:   {unit_cost: 4.10, per_latte: 0.30, per_iced: 0.35, suppliers: [Nordic Dairy Co, Oat Collective]}
    beans:  {unit_cost: 18.50, per_shot: 0.018, suppliers: [Peak Bean Roasters]}
  opex: {labor: 0.30, rent: 3600, electricity: {base: 900, seasonal_amp: 0.15}, other: 0.07}
  noise: {order_sd: 0.06, cost_sd: 0.02}
inject:
  - month: 6
    leaf: mix
    change: {iced_latte: +0.06, cold_brew: +0.03, drip: -0.05, latte: -0.04}
  - month: 6
    leaf: volume
    change: +0.11
distractors:
  - month: 6
    type: weather
    text: "unusually hot; 8 days above 32C"
```

Generator emits `truth.json`:

```json
{"primary_leaf": "mix", "attribution_truth": {"mix": -1380, "volume": +1920, "...": 0},
 "not_drivers": ["electricity", "unit_cost.milk"],
 "leakage_events": [], "answerable_questions": [{"class": "menu_change", "answer": "c"}]}
```

Noise is seeded so runs are reproducible. Each scenario ships with 3 seeds; pass conditions must hold on all 3.

---

## 27. Repository layout

```
fin-agent/
├── data/
│   ├── scenarios/            # yaml configs (§26)
│   └── generated/            # csv + truth.json per scenario × seed
├── engine/
│   ├── ingest.py             # csv → canonical (§5)
│   ├── reconcile.py          # §6
│   ├── graph_def.py          # GRAPH, leaves, profit_fn (§7)
│   ├── metrics.py            # DuckDB queries (§8)
│   ├── baselines.py          # robust stats + shrinkage (§12)
│   ├── shapley.py            # §10
│   ├── concentration.py      # §11
│   ├── materiality.py        # §13
│   ├── leakage.py            # §14
│   ├── sensitivity.py        # §15
│   └── directives.py         # §16
├── rcg/
│   ├── store.py              # nodes/edges tables, content addressing (§9)
│   ├── invariants.py         # §9 checks
│   └── validator.py          # numeric-token validator (§21)
├── agent/
│   ├── templates.py          # hypothesis templates (§17.1)
│   ├── investigate.py        # protocol (§17)
│   ├── belief.py             # LR update, temporal cap (§17.3)
│   ├── verdict.py            # §17.4
│   ├── tavily_tool.py        # §19
│   ├── questions.py          # §20
│   ├── memory.py             # carry-forward (§18)
│   ├── narrative.py          # findings → text
│   └── revision.py           # cross-period
├── voice/
│   ├── agent_config.json     # ElevenLabs agent definition
│   ├── server_tools.py       # FastAPI endpoints (§22)
│   └── postcall.py
├── ui/                       # dashboard + graph view
├── eval/
│   ├── generator.py          # §26
│   ├── scenarios_test.py     # pytest regression (§24)
│   └── prism_report.py
├── prism_setup.py
└── run.py                    # run.py --period 2026-08 --data data/aug/
```

`run.py` is the single entry point: it executes the full loop, writes the graph, emits findings JSON, and returns non-zero on any invariant or validator failure.

---

## 28. Build plan (48 hours, two people)

| Hours | Track A (engine) | Track B (agent + surfaces) |
|---|---|---|
| 0 to 4 | RCG store + invariants; canonical model; generator skeleton | PRISM setup, first traced no-op run; ElevenLabs agent shell with one tool |
| 4 to 10 | reconcile; metrics; baselines with priors; graph_def + profit_fn | templates; investigate loop against stub evidence; memory object |
| 10 to 16 | Shapley + sum test; concentration; materiality | belief update with temporal cap; verdict rules; narrative + validator |
| 16 to 22 | sensitivity + elasticity sweep; directives | Tavily tool with templates and tiers; questions |
| 22 to 28 | leakage rules; generator scenarios A to F | dashboard: period report, overlay, directive strip |
| 28 to 34 | scenarios G to M; regression harness | graph view; voice server tools + guardrail |
| 34 to 40 | three-period demo data (Jul / Aug / Sep); revision path | Observe → Improve → Prove rehearsal with v0.2 / v0.3 tags |
| 40 to 46 | bug fixing from regression matrix | narrative polish; voice flow rehearsal |
| 46 to 48 | freeze | demo run-through ×3 |

**Cut lines if behind at hour 24:** drop Tavily to a stubbed tool returning canned tier-2 evidence for the demo scenario; drop leakage to the two cheapest rules (duplicate, unit-cost outlier); drop the question engine to a static list computed from unresolved verdicts. Never cut: reconciliation, Shapley with sum test, RCG, validator, three-period revision, PRISM Observe → Improve → Prove.

---

## 29. Failure modes and mitigations

| Failure | Symptom | Mitigation |
|---|---|---|
| Mix as residual | mix effect looks small, "unexplained" bucket large | mix is an explicit leaf in `profit_fn`; unit test B asserts mix ≥ 80% of truth |
| Attribution does not sum | waterfall misses total | invariant 3, assertion in `shapley()` |
| Percentage ranking creeps in | electricity ranked first | materiality unit test E |
| Correlation → causation | weather "supported" from one article | temporal cap, tier rule, scenario D |
| LLM invents a figure | number in narrative not in graph | validator, scenario M, PRISM `unsourced_figure` |
| Voice diverges from dashboard | different numbers spoken | voice tools return pre-rendered validated text only |
| Priors treated as facts | "your gross margin is below normal" on month 1 | `prior_dominant` tag and mandatory phrasing |
| Accusatory leakage output | "supplier is overcharging you" | banned-word check in validator; counter-explanation mandatory |
| Context growth across periods | run slows, context overflows by month 8 | fixed-schema memory with caps; numbers never in prose |
| Quarterly aggregation destroys sequence | drift invisible | monthly grain always; quarterly is a separate level-drift pass |
| Question asks derivable fact | "did revenue go up?" | derivability check against metric nodes before emitting |
| Tavily generic search | "why are cafés unprofitable" | templates only; free-form queries rejected by the tool wrapper |
| Elasticity unstated | price rec with no assumption | simulation node requires `assumptions` field; validator checks narrative mentions volume assumption |
| Generator leaks truth to agent | agent reads truth.json | separate directories; CI asserts agent has no import path to `eval/` |

---

## 30. Success criteria and priorities

### Success
The agent consistently: detects unprompted; identifies the correct primary leaf; attributes with exact sum; names concentrating entities; keeps arithmetic out of the LLM; ranks by dollars and controllability; refuses unsupported causal claims; quantifies market-unexplained cost gaps without accusation; searches externally only to discriminate hypotheses; simulates with stated assumptions; issues directives and scores itself on them; asks high-VOI questions; revises on the record; produces identical facts across dashboard, graph and voice; passes scenarios A to P on all seeds.

### P0
RCG store + invariants · canonical model · reconciliation · metric engine · baselines with priors · driver graph + profit_fn · Shapley · concentration · materiality · investigation protocol with templates, belief update and verdict rules · memory object · three-period revision · structured findings + validator · PRISM tracing + scenarios A to E, I · ElevenLabs proactive briefing with server tools

### P1
Sensitivity + elasticity · directives + indicators · graph view · anomaly overlay · leakage (all rules) · question engine · Tavily with templates and tiers · voice follow-up + post-call · scenarios F, G, H, J to P

### P2
Quarterly level-drift pass · directive scoring and calibration · backtest harness (months 1 to 5 → predict 6) · elasticity estimation from history · learned seasonal patterns with confidence

---

## 31. Research frontier (post-hackathon)

The moat is not any single component; it is the closed loop of attribute → hypothesize → verify → direct → score → revise, with every step inspectable. The open problems, in order of value:

1. **Driver-graph inference for arbitrary businesses.** Start from a library of sector templates (café, salon, e-commerce, contractor) and learn the leaf structure from chart-of-accounts plus transaction descriptions. Structural priors plus constraint satisfaction is more tractable than full causal discovery.
2. **Elasticity and cross-elasticity estimation** from natural price experiments in the history, with hierarchical pooling across similar businesses so a single café benefits from thousands.
3. **Sector priors as a learned population model.** Replace the hand-set table in §12 with a hierarchical model fitted across customers; the shrinkage becomes empirical Bayes rather than a pseudo-count.
4. **Counterfactual outcome tracking.** When a directive is followed, estimate the treatment effect against a synthetic control built from the business's own pre-period and sector peers, so `impact_calibration` becomes a real causal estimate rather than a before/after.
5. **Owner-answer active learning.** Choose questions to maximize expected reduction in attribution uncertainty across future periods, not just the current gap.
6. **Cross-business anomaly pooling.** A supplier whose price rises above market for many customers at once is a much stronger signal than for one; that is a marketplace-level product.

---

## Appendix A. Critique log

A second reviewer's finance-side critique of the original brief was folded in. Each point, and what happened to it.

| # | Critique | Status | Where |
|---|---|---|---|
| 1 | Multiplicative materiality zeroes out large expected hits | adopted: A has floor 0.15, dollars gated then log-scaled | §13 |
| 2 | Persistence penalizes new problems, contradicts proactivity | adopted: P is a boost ≥ 1, never a gate | §13 |
| 3 | Sensitivity ignores elasticity, +$2,900 is a markup calc | already in v3; strengthened: assumption must be stated in-sentence, validator enforces | §15, §21 |
| 4 | Clean additive attribution implies no interaction; show a residual | rejected in the form stated: Shapley assigns interaction exactly, a residual bucket is the smell not the cure; adopted the concern by documenting why | §10 |
| 5 | Demo skips the traffic +15% vs revenue +11% gap | adopted: funnel leaves and `traffic_revenue_gap` rule; conversion line mandatory in narrative | §7, §13b |
| 6 | Gross vs contribution margin conflated | adopted: contribution is the leverage basis, variable shares declared per leaf | §7, §15 |
| 7 | Cash / accrual is a boolean with no adjustment logic | adopted: cutoff-window policy, audit tags | §6 |
| 8 | Cold-start abnormality is unreliable | already in v3: prior shrinkage, MAD, confidence gating | §12 |
| 9 | Scale mismatch: dollars swamp bounded factors | adopted: log-scaled D, exponents declared | §13 |
| 10 | Persistence needs attribution-level matching | adopted | §13 |
| 11 | Dollar and abnormality are correlated, product double-counts | partially adopted: exponent 0.3 on A damps it; full decorrelation is §31 work | §13 |
| 12 | Scores not comparable across runs | adopted: rescale to top = 100, raw score also shown | §13 |
| 13 | Instinct layer of expected-relationship rules | adopted as §13b, ten rules, deterministic triggers | §13b |
| 14 | Drill until one cluster explains > 50% of remaining | adopted as the stop rule in concentration: stop at the entity level where top-1 ≥ 50% or HHI ≥ 0.5 | §11 |
| 15 | Feedback loop: owner marks right / wrong / incomplete | adopted; feeds template priors and controllability, tallied per class | §18 |
| 16 | Explanation memory: "similar to March" | adopted as analog retrieval with capped LR | §18 |
| 17 | Derived features at ingest (recurring, dow, entity ids) | adopted | §5 |
| 18 | Customer concentration risk (fewer, larger customers) | adopted as `concentration_creep` rule; note that café POS data rarely has customer ids, so it fires on supplier side by default | §13b |
| 19 | Use a weighted sum instead of a product | not adopted: bounded factors with floors and a gate get the same robustness while preserving the "big AND unusual AND controllable" semantics the brief wants; documented as an alternative in `materiality.py` |  §13 |
| 20 | Pandas for the math | not adopted: DuckDB keeps full-history queries declarative and fast; Pandas is fine for the Shapley evaluator | §8 |

---

**GIDE builds it. PRISM proves it. ElevenLabs makes it conversational.**

Detect → Attribute → Concentrate → Prioritize → Investigate → Verify → Simulate → Direct → Ask → Explain → Revise → Score.
