#!/usr/bin/env python3
"""Export the four manuscript tables from the anonymous aggregate data."""

import argparse
import csv
import io
from decimal import Decimal
import json
from pathlib import Path
from statistics import mean

from gen_replay_values import (
    BENCHMARK_TRANSITIONS,
    HERE,
    REPLAY_INPUTS,
    benchmark_replay,
    fresh_values,
    quality_scores,
    require,
)


TABLE_INPUTS = HERE / "data/table_inputs.json"
COUNT_FIELDS = ("CM", "WC", "SM", "MM")


def scores(counts, cohort):
    n_pos, n_neg = cohort["n_pos"], cohort["n_neg"]
    cm, wc, sm, mm = (counts[key] for key in COUNT_FIELDS)
    require(all(type(count) is int and count >= 0 for count in (cm, wc, sm, mm)),
            "Outcomes must be non-negative integer counts")
    require(cm + wc + mm == n_pos and sm <= n_neg, "Outcome counts disagree with the cohort")
    return quality_scores(cm, wc, sm, mm, n_pos, n_neg)


def fresh_outcomes(fresh, additional_outcomes):
    outcomes = dict(additional_outcomes)
    for arm, data in fresh["arms"].items():
        counts = data["counts"]
        cm, wc = (counts["pos"][key] for key in ("correct", "wrong"))
        outcomes[arm] = {"CM": cm, "WC": wc, "MM": counts["n_pos"] - cm - wc, "SM": counts["neg"]["spurious"]}
    fallback = fresh_values(fresh)
    outcomes["null_only"] = {key: fallback[f"FreshReplay{key}"] for key in COUNT_FIELDS}
    return outcomes


def archived_interval(metric, bounds):
    low, high = (f"{value:.2f}" for value in bounds) if bounds is not None else (None, None)
    return {
        f"{metric}_delta_ci95_low_pp_archived": low,
        f"{metric}_delta_ci95_high_pp_archived": high,
    }


def quality_rows(table, outcomes, cohort, fallback_ci=None):
    reference = "T1 bf16, thinking off"
    baseline_recall = scores(outcomes["T1"], cohort)["R_m"]
    for row in table:
        arm = row["arm"]
        counts = outcomes[arm]
        result = scores(counts, cohort)
        ci = fallback_ci if arm == "null_only" else row.get("archived_recall_ci95_pp")
        yield {
            "configuration": row["configuration"],
            "companion_predictions": row.get("companion_predictions", False),
            "n_matchable": cohort["n_pos"],
            "n_no_match": cohort["n_neg"],
            "correct_matches": counts["CM"],
            "wrong_candidates": counts["WC"],
            "missed_matches": counts["MM"],
            "spurious_matches": counts["SM"],
            "precision_pct": f'{result["P"]:.2f}',
            "match_recall_pct": f'{result["R_m"]:.2f}',
            "no_match_false_match_rate_pct": f'{result["N-FMR"]:.2f}',
            "f05_pct": f'{result["F0.5"]:.2f}',
            "recall_reference": reference if ci is not None else None,
            "recall_delta_pp": f'{result["R_m"] - baseline_recall:.2f}' if ci is not None else None,
            **archived_interval("recall", ci),
        }


def pilot_baselines(diagnostics):
    for arm, seed in (("T1", 42), ("T1s43", 43)):
        record = diagnostics["benchmark"]["arms"][arm]
        yield {"row_kind": "baseline", "configuration": f"T1 bf16, seed {seed}",
               "precision_pct": f"{record['metrics']['P']:.2f}",
               "match_recall_pct": f"{record['metrics']['R_m']:.2f}",
               "spurious_matches": record["SM"], "f05_pct": f"{record['metrics']['F0.5']:.2f}"}


def pilot_rows(pilot, benchmark):
    outcomes = {**benchmark["outcomes"], **pilot["outcomes"]}
    cohort = benchmark["cohort"]
    for row in pilot["rows"]:
        deltas = []
        for pair in row["pairs"]:
            augmented, baseline = (outcomes[pair[key]] for key in ("augmented", "baseline"))
            variant_scores = scores(augmented, cohort)
            baseline_scores = scores(baseline, cohort)
            deltas.append((variant_scores["R_m"] - baseline_scores["R_m"],
                           variant_scores["F0.5"] - baseline_scores["F0.5"],
                           augmented["SM"] - baseline["SM"]))
        recall, f05, spurious = (mean(metric) for metric in zip(*deltas))
        yield {
            "row_kind": "augmentation_contrast",
            "configuration": row["configuration"],
            "n_seed_pairs": len(deltas),
            "recall_delta_pp": f"{recall:.2f}",
            **archived_interval("recall", row["archived_recall_ci95_pp"]),
            "f05_delta_pp": f"{f05:.2f}",
            **archived_interval("f05", row["archived_f05_ci95_pp"]),
            "spurious_matches_delta": spurious if len(deltas) == 1 else None,
        }


def serving_rows(serving, diagnostics):
    timing = diagnostics["benchmark"]["common_workload_serving"]
    for row in serving["rows"]:
        fallback = row.get("fallback_cohort")
        if fallback:
            proxy = diagnostics[fallback]["fallback_serving_proxies"]
            rate = proxy["archived_average_rate_proxy"]["fallback_queries_per_hour"]
            routed = proxy["routed"]
            denominator = proxy["n"]
            n_workload = timing["n"]
            weight_arm = "T1"
        else:
            rate = timing["arms"][row["common_workload_arm"]]["estimated_rows_per_hour"]
            routed, denominator = None, None
            n_workload = timing["n"]
            weight_arm = row["arm"]
        yield {
            "configuration": row["configuration"],
            "basis": row["basis"],
            "concurrency": timing["concurrency"],
            "loaded_weight_gib_archived": f"{Decimal(str(serving['archived_weights_gib'][weight_arm])):.1f}",
            "reference_timing_workload_queries": n_workload,
            "queries_per_hour_estimated": f"{rate:.0f}",
            "spark_hours_per_1000_estimated": f"{1000 / rate:.2f}",
            "routed_queries": routed,
            "routing_cohort_queries": denominator,
            "staged_throughput_measured": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for the generated CSV files")
    parser.add_argument("--check", action="store_true", help="check existing CSV files without writing")
    args = parser.parse_args()

    table = json.loads(TABLE_INPUTS.read_text(encoding="utf-8"))
    replay = json.loads(REPLAY_INPUTS.read_text(encoding="utf-8"))
    transitions = json.loads(BENCHMARK_TRANSITIONS.read_text(encoding="utf-8"))

    review = json.loads((HERE / "data/review_diagnostics.json").read_text(encoding="utf-8"))
    benchmark = replay["benchmark"]
    benchmark_counts = {**benchmark["outcomes"], **review["benchmark"]["arms"],
                        "null_only": benchmark_replay(transitions, benchmark)}
    benchmark_fallback_ci = benchmark["cascade_benchmark"]["vs_T1"]["ci"]["R_m"]
    fresh = replay["fresh"]
    fresh_counts = fresh_outcomes(fresh, table["fresh"]["outcomes"])
    fresh_selective_ci = review["fresh"]["selective_vs_off"]["result"]["ci"]["R_m"]
    tables = {
        "benchmark": list(quality_rows(
            table["benchmark_rows"], benchmark_counts, benchmark["cohort"], benchmark_fallback_ci
        )),
        "fresh": list(quality_rows(table["fresh"]["rows"], fresh_counts, fresh["cohort"], fresh_selective_ci)),
        "pilot": list(pilot_baselines(review)) + list(pilot_rows(table["pilot"], benchmark)),
        "serving": list(serving_rows(table["serving"], review)),
    }
    if not args.check:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        path = args.output_dir / f"{name}.csv"
        stream = io.StringIO(newline="")
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        rendered = stream.getvalue()
        if args.check:
            require(path.is_file() and path.read_text(encoding="utf-8") == rendered, f"{name}.csv differs")
        else:
            with path.open("w", encoding="utf-8", newline="") as destination:
                destination.write(rendered)
        print(f"{path}: {'matches' if args.check else 'written'}")


if __name__ == "__main__":
    main()
