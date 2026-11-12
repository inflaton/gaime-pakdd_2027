# Selective Thinking for Recall Recovery in Merchant Resolution

Anonymous evaluation supplement

This supplement documents **T1 selective thinking**, a two-stage merchant-resolution
policy that invokes thinking only when the first pass returns an explicit parsed null.
Its main contribution is the routing rule: accepted first-pass links, gate rejections,
and request failures keep their original outcomes. The policy is evaluated post hoc,
offline, using stored paired predictions on the benchmark and fresh cohorts; no staged
serving run was performed.

The package reproduces the policy outcomes and its fresh paired recall interval, exports
the four results tables, recomputes recovery-overlap enrichment, summarizes linking on
unresolved fresh queries, and regenerates the operating-point and training-loss figures.
A native TikZ source and standalone wrapper render the selective-thinking routing diagram.

## Reproduce

Run from this directory with Python 3.9 or later. The offline policy evaluation, overlap
analysis and table export use the standard library.

```sh
python3 gen_replay_values.py --check  # verify the bundled values without writing
python3 gen_replay_values.py          # regenerate replay_values.tex
python3 gen_review_values.py --check  # check the additional numeric table values
python3 review_analysis.py --check    # check overlap enrichment, transitions and unresolved rates
python3 review_analysis.py            # regenerate data/review_summary.json
python3 export_tables.py --output-dir tables
python3 export_tables.py --output-dir tables --check
```

Install Matplotlib to regenerate the figures.

```sh
python3 -m pip install 'matplotlib>=3.5'
python3 plot_figures.py --output-dir figures
```

- `data/replay_inputs.json` contains aggregate outcome tables, archived benchmark scores and
  intervals, serving estimates, cohort counts, and pilot settings and validation losses.
- `data/benchmark_transitions.json` contains paired outcomes for T1 with thinking off versus
  thinking on, fp8, NVFP4, and W4A16 on the retrospective evaluation subset.
- `gen_replay_values.py` checks aggregate marginals, recomputes benchmark scores, applies the
  selective-thinking rule on both cohorts, and formats the resulting values for the manuscript.
- `replay_values.tex` is the expected output for the bundled inputs.
- `export_tables.py` uses the replay inputs and `data/table_inputs.json` to write
  `benchmark.csv`, `fresh.csv`, `serving.csv`, and `pilot.csv`, corresponding to
  Tables 1–4 in the manuscript. Quality scores and point
  contrasts are computed from outcome counts. Published intervals and serving measurements
  are supplied as archived aggregates.
- `gen_review_values.py` regenerates the manuscript's additional numeric TeX values from the
  aggregate diagnostics, replay inputs and `data/study_values.tex`; `--check` verifies
  `data/review_values.tex`. These numeric files contain no manuscript prose.
- `data/review_diagnostics.json` adds aggregate recovery-set membership, paired transitions,
  archived paired intervals, unresolved link counts, and serving estimates. It contains no
  query identifiers or individual predictions. `review_analysis.py` independently recomputes
  one-sided exact hypergeometric enrichment from fixed set sizes and checks the transition
  totals and unresolved rates against `data/review_summary.json`.
- `pilot.csv` includes the two T1 seed baselines and the augmentation contrasts; the
  `row_kind` column distinguishes absolute scores from changes. `serving.csv` uses an explicit
  basis column and the same common-workload timing for thinking off/on and selective-thinking estimates.
- `plot_frontier.py` reads `data/frontier_inputs.json` for the directly labelled benchmark
  figure. `plot_figures.py` also reads `data/figure_inputs.json` to retain the supplementary
  training/validation loss curves for all four pilot runs.

## Selective-thinking routing diagram

`fig_selective_thinking.tex` is the native vector routing diagram. It separates the parsed
explicit-null test from the acceptance gate and shows the retained first-pass path and
the optional thinking-on path. To render it, use a LaTeX installation with TikZ and the
`standalone` class:

```sh
mkdir -p figures
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=figures \
  -jobname=fig_selective_thinking render_selective_thinking.tex
```

The output is `figures/fig_selective_thinking.pdf`. This is a policy diagram, not evidence
of measured online routing performance. The two Python-generated figures remain
`fig_frontier.pdf` and the supplementary `fig_pilot_losses.pdf`.

## Evaluation protocol

**Retrospective expert benchmark.** A stratified split reserved 450 of 2,000 expert-labelled
queries for the augmentation pilot, with near-duplicate groups kept together. The 1,550
evaluation queries include 1,010 with an acceptable candidate in the retrieved set and 540
with none. The latter include retrieval misses. The benchmark informed earlier curator and
gate choices. The pilot also used 40 external few-shot exemplars as training additions.

**Fresh audit.** The 1,000 fresh queries are disjoint from the benchmark and training set.
Two LLM auditors saw the same descriptors and candidates independently, with student
outputs and retrieval scores withheld. A matchable query requires at least one commonly
accepted candidate. A no-match query requires both auditors to mark zero candidates as
acceptable or uncertain. There are 434 matchable, 357 no-match, and 209 unresolved queries.
Quality scores use the 791 resolved queries and measure agreement with this audit reference.

**Candidate selection and scoring.** The retriever returns 19–21 candidates. The judge
proposes an ID or returns null. The acceptance gate requires a candidate selection, a
matching name with confidence at least 0.70, and zero contradictory location flags.
Rejections and failed requests score as abstentions. On matchable queries, `CM`, `WC`, and
`MM` count correct selections, wrong-candidate selections, and abstentions. `SM` counts
spurious selections on no-match queries. Recall is `CM / (CM + WC + MM)`, precision is
`CM / (CM + WC + SM)`, and the no-match false-match rate is `SM / n_neg`. The script reports
these as percentages and computes F0.5, which weights precision more than recall.

**T1 selective thinking.** The first pass is T1 with thinking off. The offline policy
evaluation substitutes the stored paired thinking-on outcome only after an explicit
parsed null. A selected candidate, gate rejection, or failed request keeps its first-pass
outcome. Thus an accepted first-pass link is never
replaced; a first-pass gate rejection or request failure stays an abstention. The route
trigger is a parsed explicit null ID, not every downstream abstention. Both passes use
the same checkpoint, query, candidate set, prompt and fixed acceptance gate; only the
thinking mode changes. Rows in the joint outcome tables denote
thinking off and columns denote the corresponding comparison configuration. `pos` and `neg`
refer to the matchable and no-match reference classes. In the retrospective tables, `gate`
groups rejections and `failure` groups failed requests and invalid verdicts. The script
checks the arm totals and applies the routing rule to the thinking comparison counts.

## Results and interpretation

| Cohort and policy | Recall (%) | Wrong candidates | Spurious links | Routed to thinking |
|---|---:|---:|---:|---:|
| Retrospective, thinking off | 86.73 | 4 | 9 | 0 / 1,550 |
| Retrospective, always-on thinking | 95.35 | 2 | 26 | 1,550 / 1,550 |
| Retrospective, T1 selective thinking | 96.04 | 5 | 27 | 661 / 1,550 |
| Fresh, thinking off | 83.41 | 2 | 0 | 0 / 1,000 |
| Fresh, always-on thinking | 91.47 | 1 | 0 | 1,000 / 1,000 |
| Fresh, T1 selective thinking | 93.09 | 3 | 0 | 626 / 1,000 |

Both quality CSVs use ordinary T1 with thinking off as their recall-change reference.
The fresh selective-thinking row compares 404 versus 362 correct matches on 434 matchable
queries: 42 gains and no lost correct matches. Its **+9.68-point** recall change has an
archived **95% interval [+6.95, +12.61]**, computed by the same aligned paired row-bootstrap
convention as the other fresh contrasts: 4,000 resamples, NumPy `default_rng(42)`, over the
791 resolved queries in their original order. This interval conditions on the post hoc
routing rule. It differs from the selective-minus-always-on contrast reported below;
the latter retains its separately reproduced interval.

Among the reported T1 configurations, selective thinking has the highest observed recall
on both cohorts; this is not a claim about every model or unreported configuration. On the
benchmark its recall difference against always-on thinking is +0.69 percentage points
(archived 95% paired interval 0.00 to +1.50), so this benchmark interval includes zero.
Its F0.5 point estimate is slightly lower on both cohorts.

The fresh routing denominator includes the unresolved queries. Recall and error counts use
the resolved reference. Selective thinking on the fresh slice gains nine correct selections and loses two
relative to always-on thinking, for a recall change of **+1.61 percentage points**.
The interval **[+0.23, +3.13]** comes from 4,000 paired percentile resamples, using seed 42.
Each draw resamples the 791 resolved queries from the grouped counts of matchable gains,
losses, ties, and no-match queries. This exploratory interval conditions on the rule selected
after inspecting the transitions. The prespecified fresh thinking-on versus thinking-off
comparison has a different estimand and interval.

The retrospective transition tables reproduce 970 correct selections for benchmark selective thinking,
5 wrong candidates, and 27 spurious links. They also show that 58 of the 59 newly correct
NVFP4 selections replaced an explicit null. The retrospective paired intervals come from the
study's query-level analysis and are stored as reported.

**Recovery overlap.** Thinking recovers 98 of the 134 matchable queries ordinary T1 does not
get correct (73.1%). Conditioning on that recovery rate and fixed recovery-set sizes, its
54 overlaps with NVFP4's 59 recoveries exceed the uniform-overlap expectation of 43.15
(one-sided exact hypergeometric p = 0.0000114); 48 overlaps with A42's 51 exceed 37.30
(p = 0.0000060). This is exploratory enrichment under a uniform-overlap reference, not
independent validation of a causal mechanism.

On the resolved fresh slice, thinking recovers 44 of 72 noncorrect queries (61.1%). Its
14 overlaps with NVFP4's 18 recoveries compare with expectation 11.0 (p = 0.0793), and
seven overlaps with A42's nine compare with 5.5 (p = 0.2368). The enrichment beyond the
base recovery rate is therefore a benchmark finding; fresh overlap does not distinguish
it from the uniform-overlap reference at the conventional 5% level.

**Unresolved fresh queries.** Among 209 queries without an agreed reference, selective
thinking accepts 30 links (14.35%), compared with nine (4.31%) for thinking off and
28 (13.40%) for always-on thinking. The zero-shot base accepts 53 (25.36%) and local
120B 54 (25.84%). The policy therefore links more often than either T1 reference on
this slice, where correctness is unresolved. Always-on thinking changes 24 final
decisions relative to thinking off: 21 thinking-only links,
two off-only links, and one different-ID link. These counts describe linking, not accuracy.

**Augmentation transitions.** On the benchmark A42 gains 51 correct matches and loses 15;
on fresh it gains nine and loses 36, all fresh gains/losses involving explicit nulls.
Thinking introduces 18 benchmark-negative spurious links and removes one, for a net
increase of 17. Independent expert adjudication of the 24 unresolved fresh changes and
19 changed benchmark-negative decisions is not provided by this package.

## Training and serving settings

The companion study applied two zero-shot teachers to 3,600 queries from a pool separate
from the fresh audit. Gemma 4 31B used thinking off and Muse Glimmer 30B used low reasoning
effort. Both verdicts had to parse. A positive label required both to select the same
candidate at a name-confidence threshold of 0.86. A negative label required neither to
make an accepted selection at 0.80. Curation kept 2,830 examples and deferred 770.

The curated T1 training set has 2,550 teacher-labelled examples (877 positive, 1,673 negative).
The validation set has 280 examples (100 positive, 180 negative). All four pilot arms measure
validation loss on the same 150-example subset. The expert-augmented training set adds 490
queries (322 matchable, 168 no match) for 3,040 examples total. The runs use seeds 42 and 43,
bf16, verdict-token loss, and rank-8 LoRA on attention and MLP projections (alpha 16, dropout 0).
The peak learning rate is 0.0001 with cosine decay and 10% warmup. The token cutoff is 10,240.
Each run trains for one epoch and 160 updates. With microbatch 1, gradient accumulation is 16
for T1 and 19 for augmentation. The snapshot records the final validation loss of each arm.

Local serving uses a DGX Spark with 128 GB unified memory and 16 concurrent requests, on
vLLM `0.28.1rc1.dev437` (build `e962733`). T1 thinking on and off use the same bf16 base, LoRA
adapter, and greedy request settings. The fresh thinking-off baseline comes from an earlier
run. The common-workload rate estimates use 2,000 requests and `3600 * concurrency / mean
request seconds`, assuming all worker slots stay busy. The archived bf16 rates are 1,713.85
rows/hour with thinking off and 199.90 with thinking on, an estimated slowdown of 8.6×.
The separate fresh wall-clock measurement covers 990 requests in 297 minutes after the
smoke test, or approximately 200 rows/hour. These rates describe individual configurations.
End-to-end throughput and queueing for the two-stage selective-thinking policy remain to be measured.

The serving CSV places the focal configurations on one timing basis:

| Configuration | Basis | Estimated queries/h | Estimated Spark-hours/1,000 |
|---|---|---:|---:|
| T1 bf16, off | Common-workload estimate | 1,714 | 0.58 |
| T1 bf16, on | Common-workload estimate | 200 | 5.00 |
| T1 selective thinking, benchmark | Additive routing estimate | 368 | 2.72 |
| T1 selective thinking, full fresh | Additive routing estimate | 269 | 3.72 |
| T1 fp8 | Common-workload estimate | 2,266 | 0.44 |
| T1 NVFP4 | Common-workload estimate | 1,997 | 0.50 |

The additive selective-thinking model uses `1 / off_rate + routed_share / on_rate` hours per query,
with routed shares 661/1,550 and 626/1,000. It assumes routed requests take the benchmark
mean thinking duration. The resulting occupied-slot estimates are 54.3% and 74.3% of
always-on thinking, equivalent to **1.84 and 1.35 times its estimated capacity**. These are
capacity-model ratios, not measured end-to-end speedups. An offline calculation using
same-query request latencies yields 54.7% and 70.4%; neither arithmetic model measures
GPU service time or end-to-end staged throughput. Archived request latency
can include queueing/retries, and routing changes batching and prefix caching.

## Release scope

The package contains aggregate counts, settings, and analysis code. Production descriptors,
candidate records, per-query predictions, row-level identifiers and hashes, private prompts,
training rows, and checkpoints remain in the controlled environment. The offline commands
start from the aggregate snapshot. Training, inference, and prospective deployment require
the corresponding study inputs and environment.
