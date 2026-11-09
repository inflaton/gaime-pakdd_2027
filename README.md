# Merchant-resolution evaluation supplement

This supplement documents the evaluation protocol and provides an offline analysis of
aggregate outcomes for a local merchant-resolution judge. It reconstructs the null-only
fallback on both evaluation cohorts, reproduces the fresh fallback's paired recall interval,
exports the four results tables, and regenerates the operating-point and training-loss figures.

## Reproduce

Run from this directory with Python 3.9 or later. The replay and table export use the
standard library.

```sh
python3 gen_replay_values.py --check  # verify the bundled values without writing
python3 gen_replay_values.py          # regenerate replay_values.tex
python3 export_tables.py --output-dir tables
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
  fallback rule on both cohorts, and formats the resulting values for the manuscript.
- `replay_values.tex` is the expected output for the bundled inputs.
- `export_tables.py` uses the replay inputs and `data/table_inputs.json` to write
  `benchmark.csv`, `fresh.csv`, `pilot.csv`, and `serving.csv`. Quality scores and point
  contrasts are computed from outcome counts. Published intervals and serving measurements
  are supplied as archived aggregates.
- `plot_figures.py` reads `data/figure_inputs.json` to write `fig_frontier.pdf` and
  `fig_pilot_losses.pdf`. The input records the plotted operating points and training and
  validation loss by optimizer step for all four pilot runs.

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

**Fallback replay.** The first pass is T1 with thinking off. The replay uses the paired
thinking-on outcome only after an explicit parsed null. A selected candidate, gate rejection,
or failed request keeps its first-pass outcome. Rows in the joint outcome tables denote
thinking off and columns denote the corresponding comparison configuration. `pos` and `neg`
refer to the matchable and no-match reference classes. In the retrospective tables, `gate`
groups rejections and `failure` groups failed requests and invalid verdicts. The script
checks the arm totals and applies the routing rule to the thinking comparison counts.

## Results and interpretation

| Cohort and policy | Recall (%) | Wrong candidates | Spurious links | Routed to thinking |
|---|---:|---:|---:|---:|
| Retrospective, thinking off | 86.73 | 4 | 9 | 0 / 1,550 |
| Retrospective, always-on thinking | 95.35 | 2 | 26 | 1,550 / 1,550 |
| Retrospective, null-only replay | 96.04 | 5 | 27 | 661 / 1,550 |
| Fresh, thinking off | 83.41 | 2 | 0 | 0 / 1,000 |
| Fresh, always-on thinking | 91.47 | 1 | 0 | 1,000 / 1,000 |
| Fresh, null-only replay | 93.09 | 3 | 0 | 626 / 1,000 |

The fresh routing denominator includes the unresolved queries. Recall and error counts use
the resolved reference. The fresh fallback gains nine correct selections and loses two
relative to always-on thinking, for a recall change of **+1.61 percentage points**.
The interval **[+0.23, +3.13]** comes from 4,000 paired percentile resamples, using seed 42.
Each draw resamples the 791 resolved queries from the grouped counts of matchable gains,
losses, ties, and no-match queries. This exploratory interval conditions on the rule selected
after inspecting the transitions. The prespecified fresh thinking-on versus thinking-off
comparison has a different estimand and interval.

The retrospective transition tables reproduce the benchmark fallback's 970 correct selections,
5 wrong candidates, and 27 spurious links. They also show that 58 of the 59 newly correct
NVFP4 selections replaced an explicit null. The retrospective paired intervals come from the
study's query-level analysis and are stored as reported.

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
End-to-end throughput and queueing for the two-stage fallback remain to be measured.

## Release scope

The package contains aggregate counts, settings, and analysis code. Production descriptors,
candidate records, per-query predictions, row-level identifiers and hashes, private prompts,
training rows, and checkpoints remain in the controlled environment. The offline commands
start from the aggregate snapshot. Training, inference, and prospective deployment require
the corresponding study inputs and environment.
