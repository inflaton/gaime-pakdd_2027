#!/usr/bin/env python3
"""Generate study and selective-thinking values from aggregate paired outcomes."""

import argparse
from collections import Counter
import json
from pathlib import Path
from random import Random
from statistics import quantiles


HERE = Path(__file__).resolve().parent
REPLAY_INPUTS = HERE / "data/replay_inputs.json"
BENCHMARK_TRANSITIONS = HERE / "data/benchmark_transitions.json"
OUT = HERE / "replay_values.tex"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def quality_scores(cm, wc, sm, mm, n_pos, n_neg):
    """Return precision, match recall, no-match false-match rate, and F0.5 as percentages."""
    return {
        "P": 100 * cm / (cm + wc + sm),
        "R_m": 100 * cm / n_pos,
        "N-FMR": 100 * sm / n_neg,
        "F0.5": 125 * cm / (1.25 * cm + wc + sm + 0.25 * (wc + mm)),
    }


def replay_counts(table, off, on, n):
    """Validate paired marginals, then use the thinking verdict only after a raw null."""
    require(table.keys() == off.keys() and "null" in off, "Unexpected thinking-off categories")
    variant_totals = Counter()
    routed_outcomes = Counter()
    for before, row in table.items():
        require(row.keys() == on.keys(), "Unexpected thinking-on categories")
        require(all(type(count) is int and count >= 0 for count in row.values()), "Invalid paired count")
        require(sum(row.values()) == off[before], "Thinking-off marginal disagrees with paired counts")
        for after, count in row.items():
            variant_totals[after] += count
            routed_outcomes[after if before == "null" else before] += count
    require(dict(variant_totals) == on, "Thinking-on marginal disagrees with paired counts")
    require(sum(routed_outcomes.values()) == n, "Paired counts disagree with the resolved denominator")
    return routed_outcomes


def fallback_recall_interval(gains, losses, n_pos, n_neg, bootstrap):
    """Bootstrap paired recall from positive gains, losses, ties and negatives."""
    weights = (gains, losses, n_pos - gains - losses, n_neg)
    rng = Random(bootstrap["seed"])
    draws = []
    for _ in range(bootstrap["resamples"]):
        sample = Counter(rng.choices(range(4), weights=weights, k=n_pos + n_neg))
        sampled_positives = sample[0] + sample[1] + sample[2]
        if sampled_positives:
            draws.append(100 * (sample[0] - sample[1]) / sampled_positives)
    require(bootstrap["level"] == 95, "Expected a 95% bootstrap interval")
    bounds = quantiles(draws, n=40, method="inclusive")
    return 100 * (gains - losses) / n_pos, bounds[0], bounds[-1]


def fresh_values(bundle):
    cohort = bundle["cohort"]
    n, n_pos, n_neg = (cohort[key] for key in ("n_total", "n_pos", "n_neg"))
    n_resolved, n_unresolved = cohort["n_resolved"], cohort["n_unresolved"]
    require(n_resolved == n_pos + n_neg and n == n_resolved + n_unresolved, "Inconsistent cohort denominators")

    contrast = bundle["contrasts"]["think_vs_off"]
    require((contrast["base"], contrast["variant"]) == ("T1", "T1_think"), "Unexpected paired comparison")
    off, on = (bundle["arms"][arm] for arm in ("T1", "T1_think"))
    for arm in (off, on):
        require(arm["all1000"]["rows"] == n, "Arm does not cover the full fresh cohort")
        require((arm["counts"]["n_pos"], arm["counts"]["n_neg"]) == (n_pos, n_neg), "Arm denominator differs")
    pos, neg = (
        replay_counts(contrast["transitions"][f"{side}_crosstab_base_to_variant"],
                      off["counts"][side], on["counts"][side], denom)
        for side, denom in (("pos", n_pos), ("neg", n_neg))
    )
    routed = off["all1000"]["null"]
    routed_resolved = off["counts"]["pos"]["null"] + off["counts"]["neg"]["null"]
    require(0 <= routed - routed_resolved <= n_unresolved, "Inconsistent explicit-null routing counts")

    agreement = contrast["agreement_pct"]
    matching = [count for count in range(n_unresolved + 1)
                if round(100 * count / n_unresolved, 2) == agreement["unresolved"]]
    require(len(matching) == 1, "Cannot recover a unique unresolved agreement count from the rounded percentage")
    changed = n_unresolved - matching[0]
    off_only = agreement["unresolved_base_selects_variant_not"]
    on_only = agreement["unresolved_variant_selects_base_not"]
    competing = changed - off_only - on_only
    both_selected = off["unresolved_selected"] - off_only
    require(both_selected == on["unresolved_selected"] - on_only and 0 <= competing <= both_selected,
            "Inconsistent unresolved selection counts")

    cm, wc, sm = pos["correct"], pos["wrong"], neg["spurious"]
    mm = n_pos - cm - wc
    scores = quality_scores(cm, wc, sm, mm, n_pos, n_neg)
    pos_table = contrast["transitions"]["pos_crosstab_base_to_variant"]
    gains = off["counts"]["pos"]["correct"] - pos_table["correct"]["correct"]
    losses = sum(row["correct"] for before, row in pos_table.items()
                 if before not in ("correct", "null"))
    delta_recall, delta_lo, delta_hi = fallback_recall_interval(
        gains, losses, n_pos, n_neg, bundle["bootstrap"]
    )
    return {
        "FreshReplayRouted": routed,
        "FreshReplayRouteShare": f"{100 * routed / n:.1f}",
        "FreshReplayRoutedResolved": routed_resolved,
        "FreshReplayCM": cm,
        "FreshReplayWC": wc,
        "FreshReplayMM": mm,
        "FreshReplaySM": sm,
        "FreshReplayR": f'{scores["R_m"]:.2f}',
        "FreshReplayDeltaR": f"{delta_recall:+.2f}",
        "FreshReplayDeltaRLo": f"{delta_lo:+.2f}",
        "FreshReplayDeltaRHi": f"{delta_hi:+.2f}",
        "FreshReplayGains": gains,
        "FreshReplayLosses": losses,
        "FreshThinkWC": on["counts"]["pos"]["wrong"],
        "FreshReplayP": f'{scores["P"]:.2f}',
        "FreshReplayF": f'{scores["F0.5"]:.2f}',
        "FreshUnresolvedChanged": changed,
        "FreshUnresolvedCompeting": competing,
    }


def benchmark_replay(transitions, bundle):
    """Check paired arm totals and reconstruct the benchmark fallback."""
    outcomes = bundle["outcomes"]
    cohort = bundle["cohort"]
    n_pos, n_neg = cohort["n_pos"], cohort["n_neg"]

    def score_counts(pos, neg):
        cm, wc = pos["correct"], pos["wrong"]
        return {"CM": cm, "WC": wc, "SM": neg["spurious"], "MM": n_pos - cm - wc}

    def check_counts(arm, counts):
        require(all(outcomes[arm][key] == value for key, value in counts.items()),
                f"{arm}: transition counts disagree with scores")

    expected_arms = {"T1_think", "T1_fp8", "T1_nvfp4", "T1_w4a16"}
    require(transitions.keys() == expected_arms, "Unexpected retrospective transition comparisons")
    for arm, tables in transitions.items():
        replayed = {}
        base = {}
        variant = {}
        for side, n, categories in (
            ("pos", n_pos, {"correct", "wrong", "null", "gate", "failure"}),
            ("neg", n_neg, {"spurious", "null", "gate", "failure"}),
        ):
            table = tables[side]
            require(table.keys() == categories, f"{arm}: unexpected {side} categories")
            base[side] = {before: sum(row.values()) for before, row in table.items()}
            variant[side] = {after: sum(row.get(after, 0) for row in table.values()) for after in categories}
            replayed[side] = replay_counts(table, base[side], variant[side], n)
            require(base[side]["null"] == bundle["first_pass_explicit_nulls"][side],
                    f"{arm}: inconsistent first-pass null count")
        check_counts("T1", score_counts(**base))
        check_counts(arm, score_counts(**variant))
        if arm == "T1_think":
            fallback = score_counts(**replayed)
            check_counts("null_only", fallback)
    return fallback


def benchmark_values(bundle, fresh_wall_clock, transitions):
    cohort = bundle["cohort"]
    n_pos, n_neg = cohort["n_pos"], cohort["n_neg"]
    require(cohort["n"] == n_pos + n_neg, "Inconsistent retrospective denominators")
    for label, outcome in bundle["outcomes"].items():
        c, w, s, m = (outcome[k] for k in ("CM", "WC", "SM", "MM"))
        require(all(type(count) is int and count >= 0 for count in (c, w, s, m)),
                f"{label}: invalid retrospective outcome count")
        require(c + w + m == n_pos and s <= n_neg, f"{label}: invalid retrospective marginals")
        scores = {key: round(value, 2) for key, value in quality_scores(c, w, s, m, n_pos, n_neg).items()}
        require(scores == outcome["metrics"], f"{label}: retrospective scores disagree with counts")

    fallback = benchmark_replay(transitions, bundle)
    cascade = bundle["cascade_benchmark"]
    require(cascade["n_routed"] == sum(bundle["first_pass_explicit_nulls"].values()),
            "Retrospective routing count disagrees with explicit nulls")
    scores = quality_scores(fallback["CM"], fallback["WC"], fallback["SM"], fallback["MM"], n_pos, n_neg)
    require(cascade["metrics"] == {key: round(value, 2) for key, value in scores.items()}
            and cascade["SM"] == fallback["SM"],
            "Retrospective fallback summaries disagree")
    delta = 100 * (fallback["CM"] - bundle["outcomes"]["T1"]["CM"]) / n_pos
    require(round(delta, 2) == cascade["vs_T1"]["delta"]["R_m"], "Retrospective fallback delta disagrees")
    lo, hi = cascade["vs_T1"]["ci"]["R_m"]
    timing = bundle["benchmark_quality_timing"]["arms"]
    slowdown = timing["T1"]["estimated_rows_per_hour"] / timing["T1_think"]["estimated_rows_per_hour"]
    rows, minutes = (fresh_wall_clock[key] for key in ("rows", "minutes"))
    return {
        "PakddCascadeP": f'{scores["P"]:.2f}',
        "PakddCascadeF": f'{scores["F0.5"]:.2f}',
        "PakddCascadeSm": fallback["SM"],
        "PakddCascadeDeltaR": f"{delta:+.2f}",
        "PakddCascadeDeltaRLo": f"{lo:+.2f}",
        "PakddCascadeDeltaRHi": f"{hi:+.2f}",
        "PakddThinkSlowdown": f"{slowdown:.1f}",
        "PakddFreshThinkRate": f"{60 * rows / minutes:,.0f}",
    }


def companion_values(companion):
    return {
        "PakddFullStuR": f'{companion["full_student_recall"]:.2f}',
        "PakddFreshFullStuR": f'{companion["fresh_full_student_recall"]:.2f}',
        "PakddFullQwenR": f'{companion["full_qwen_recall"]:.2f}',
        "PakddPoolEligible": f'{companion["eligible_queries"]:,}',
        "PakddAgreementNegErr": companion["agreement_negative_errors"],
        "PakddAgreementErr": companion["agreement_errors"],
        "PakddCalibN": companion["calibration_examples"],
    }


def training_values(pilot):
    counts = pilot["counts"]
    config = pilot["config"]
    values = {
        "PakddTrainPos": f'{counts["train"]["pos"]:,}',
        "PakddTrainNeg": f'{counts["train"]["neg"]:,}',
        "PakddDevPos": f'{counts["dev"]["pos"]:,}',
        "PakddDevNeg": f'{counts["dev"]["neg"]:,}',
        "PakddDevEvalN": pilot["shared_dev_examples"],
        "PakddLoraAlpha": config["lora_alpha"],
        "PakddLoraDropout": f'{config["lora_dropout"]:g}',
        "PakddLearningRate": f'{config["learning_rate"]:g}',
        "PakddWarmupPct": f'{100 * config["warmup_ratio"]:g}',
        "PakddCutoff": f'{config["cutoff_len"]:,}',
        "PakddEpochs": f'{config["num_train_epochs"]:g}',
        "PakddMicrobatch": config["per_device_train_batch_size"],
        "PakddLogSteps": config["logging_steps"],
        "PakddEvalSteps": config["eval_steps"],
    }
    final_losses = pilot["final_eval_loss"]
    for arm, label in (("T1", "StuA"), ("T1-X490", "AugA"), ("T1-s43", "StuB"), ("T1-X490-s43", "AugB")):
        values[f"Pakdd{label}DevLoss"] = f"{final_losses[arm]:.5f}"
    return values


def generate():
    inputs = json.loads(REPLAY_INPUTS.read_text(encoding="utf-8"))
    transitions = json.loads(BENCHMARK_TRANSITIONS.read_text(encoding="utf-8"))
    values = {
        **fresh_values(inputs["fresh"]),
        **benchmark_values(inputs["benchmark"], inputs["fresh_wall_clock"], transitions),
        **companion_values(inputs["companion"]),
        **training_values(inputs["pilot"]),
    }
    lines = [
        "% Generated by gen_replay_values.py from data/replay_inputs.json.",
        "% The fresh policy was selected post hoc and evaluated on stored predictions. No staged throughput was measured.",
    ]
    lines.extend(rf"\newcommand{{\{name}}}{{{value}}}" for name, value in values.items())
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the generated TeX without writing it")
    args = parser.parse_args()
    rendered = generate()
    if args.check:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != rendered:
            print(f"{OUT.name} differs from the local study inputs")
            return 1
        print(f"{OUT.name} matches; retrospective scores and offline selective-thinking outcomes verified")
        return 0
    OUT.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
