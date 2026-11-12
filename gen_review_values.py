#!/usr/bin/env python3
"""Generate internal-revision values from verified aggregate diagnostics.

Intervals are copied from archived paired bootstrap results; this script does
not fit a model or estimate new bootstrap intervals. Python standard library.
"""
import argparse
import json
import math
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
OUT = HERE / "data/review_values.tex"


def generate():
    diagnostics = json.loads((HERE / "data/review_diagnostics.json").read_text())
    replay = json.loads((HERE / "data/replay_inputs.json").read_text())
    study = (HERE / "data/study_values.tex").read_text()
    values = {}

    def number(name, value, digits=2, signed=False):
        rendered = f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"
        if rendered.startswith("-"):
            rendered = "$-$" + rendered[1:]
        values[name] = rendered

    def count(name, value):
        values[name] = f"{value:,}"

    def probability(name, value):
        if 0 < value < 0.001:
            exponent = math.floor(math.log10(value))
            values[name] = r"\mbox{" + rf"${value / 10 ** exponent:.2f}\times10^{{{exponent}}}$" + "}"
        else:
            number(name, value, 2)

    def arm(prefix, record):
        for suffix, metric in (("P", "P"), ("R", "R_m"), ("Fmr", "N-FMR"), ("F", "F0.5")):
            number(prefix + suffix, record["metrics"][metric])
        for suffix, field in (("Cm", "CM"), ("Wc", "WC"), ("Sm", "SM"), ("Mm", "MM")):
            count(prefix + suffix, record[field])

    def contrast(prefix, record, metric):
        result = record["result"]
        number(prefix, result["delta"][metric], signed=True)
        number(prefix + "Lo", result["ci"][metric][0], signed=True)
        number(prefix + "Hi", result["ci"][metric][1], signed=True)

    benchmark, fresh = diagnostics["benchmark"], diagnostics["fresh"]
    count("rvRateUnit", fresh["cohort"]["n_total"])
    for prefix, key in (("rvBase", "ZS"), ("rvSeedB", "T1s43"), ("rvAugA", "A42"), ("rvAugB", "A43")):
        arm(prefix, benchmark["arms"][key])
    for prefix, key in (("rvFreshBase", "ZS"), ("rvFreshLocal", "R120")):
        arm(prefix, fresh["arms"][key])
    for metric, suffix in (("R_m", "R"), ("N-FMR", "Fmr"), ("P", "P"), ("F0.5", "F")):
        contrast("rvProdDelta" + suffix, benchmark["archived_contrasts"]["T1_think-PROD"], metric)
    contrast("rvThinkDeltaFmr", benchmark["archived_contrasts"]["T1_think-T1"], "N-FMR")
    contrast("rvBaseDeltaR", benchmark["archived_contrasts"]["ZS-T1"], "R_m")
    for prefix, key in (("rvFreshBaseDeltaR", "ZS_vs_T1"), ("rvFreshLocalDeltaR", "R120_vs_T1")):
        contrast(prefix, fresh["archived_contrasts"][key], "R_m")
    number("rvSeedRecallSpread", benchmark["arms"]["T1"]["metrics"]["R_m"]
           - benchmark["arms"]["T1s43"]["metrics"]["R_m"])

    for cohort, section in (("Bench", benchmark), ("Fresh", fresh)):
        for label, key in (("AugA", "A42-T1"), ("AugB", "A43-T1s43" if cohort == "Bench" else "A43-T1"),
                           ("Think", "T1_think-T1")):
            transition = section["transitions"][key]
            prefix = "rv" + cohort + label
            for suffix, field in (("Gains", "newly_correct"), ("Losses", "lost_correct"),
                                  ("NewSm", "new_spurious"), ("RemovedSm", "removed_spurious")):
                count(prefix + suffix, transition[field])
            for category in ("null", "wrong"):
                count(prefix + category.title() + "Gains", transition["newly_correct_from"].get(category, 0))
                count(prefix + category.title() + "Losses", transition["lost_correct_to"].get(category, 0))

        proxy = section["fallback_serving_proxies"]
        for label, key in (("", "archived_average_rate_proxy"), ("Latency", "observed_request_latency_proxy")):
            record = proxy[key]
            prefix = "rv" + cohort + "Fallback" + label
            number(prefix + "Work", 100 * record["fallback_to_always_on_occupied_slot_time_ratio"], 1)
            number(prefix + "Rate", record["fallback_queries_per_hour"], 0)
            number(prefix + "Hours", 1000 / record["fallback_queries_per_hour"])
        fallback = section["fallback"] if cohort == "Bench" else section["fallback_resolved"]
        count("rv" + cohort + "Abstentions", fallback["first_pass_abstentions"])
        number("rv" + cohort + "FallbackF", fallback["summary"]["metrics"]["F0.5"])

    overlap = benchmark["rescue_overlap"]
    for prefix, key in (("rvThinkRescues", "T1_think"), ("rvNvRescues", "T1_nvfp4"), ("rvAugRescues", "A42")):
        count(prefix, overlap["counts"][key])
    for prefix, key in (("rvThinkAugOverlap", "T1_think+A42"), ("rvThinkNvOverlap", "T1_think+T1_nvfp4")):
        count(prefix, overlap["pairwise_intersections"][key])
    count("rvSharedAll", overlap["exact_membership"]["T1_think+T1_nvfp4+A42"])
    count("rvRescueUnion", overlap["union"])
    count("rvAugUniqueRescues", overlap["exact_membership"]["A42"])
    number("rvThinkAugCoverage", 100 * overlap["pairwise_intersections"]["T1_think+A42"] / overlap["counts"]["A42"], 1)
    number("rvThinkNvCoverage", 100 * overlap["pairwise_intersections"]["T1_think+T1_nvfp4"] / overlap["counts"]["T1_nvfp4"], 1)
    for prefix, section in (("rvBench", benchmark), ("rvFresh", fresh)):
        enrichment = section["rescue_overlap"]["enrichment_vs_thinking"]
        count(prefix + "Misses", enrichment["population"])
        count(prefix + "ThinkRescues", enrichment["thinking_rescues"])
        number(prefix + "ThinkRescueShare", enrichment["thinking_rescue_rate_pct"], 1)
        for label, key in (("Nv", "T1_nvfp4"), ("Aug", "A42")):
            comparison = enrichment["comparisons"][key]
            count(prefix + label + "Rescues", comparison["variant_rescues"])
            count(prefix + label + "Overlap", comparison["observed_overlap"])
            number(prefix + label + "ExpectedOverlap", comparison["expected_overlap"], 1)
            probability(prefix + label + "OverlapP", comparison["p_upper"])
    unresolved = fresh["unresolved_acceptance"]
    count("rvUnresolvedN", unresolved["n"])
    for label, key in (("Stu", "T1"), ("Think", "T1_think"), ("Base", "ZS"), ("Local", "R120")):
        count("rvUnresolved" + label + "Links", unresolved["arms"][key]["accepted"])
        number("rvUnresolved" + label + "Pct", unresolved["arms"][key]["accepted_pct"], 1)
    number("rvBaseFmrRatio", (benchmark["arms"]["ZS"]["SM"] / benchmark["cohort"]["n_neg"])
           / (fresh["arms"]["ZS"]["SM"] / fresh["cohort"]["n_neg"]), 1)
    n_neg = fresh["cohort"]["n_neg"]
    number("rvTwoSidedUpper", 100 * (1 - 0.025 ** (1 / n_neg)))
    number("rvOneSidedUpper", 100 * (1 - 0.05 ** (1 / n_neg)))
    number("rvTrainPositiveShare", 100 * replay["pilot"]["counts"]["train"]["pos"]
           / sum(replay["pilot"]["counts"]["train"].values()), 1)
    for prefix, section in (("rvBenchPositiveShare", benchmark), ("rvFreshPositiveShare", fresh)):
        cohort = section["cohort"]
        number(prefix, 100 * cohort["n_pos"] / (cohort["n_pos"] + cohort["n_neg"]), 1)
    rates = benchmark["fallback_serving_proxies"]["archived_average_rate_proxy"]
    number("rvOffHours", 1000 / rates["off_queries_per_hour"])
    number("rvThinkHours", 1000 / rates["think_queries_per_hour"])
    for label, key in (("Fp", "T1_fp8"), ("Nv", "T1_nvfp4")):
        rate = benchmark["common_workload_serving"]["arms"][key]["estimated_rows_per_hour"]
        count("rv" + label + "CommonRate", round(rate))
        number("rv" + label + "CommonHours", 1000 / rate)
    count("rvFreshGateRetained", fresh["fallback_all1000_routing"]["retained_gate_rejections"])

    # Same-harness throughput and weight-memory values retain their frozen source.
    for prefix, macro in (("rvStuHarnessHours", "vsStuCSixteen"), ("rvFpHarnessHours", "vsFpCSixteen"),
                          ("rvNvHarnessHours", "vsNvCSixteen"), ("rvWqHarnessHours", "vsWqCSixteen"),
                          ("rvBigHarnessHours", "vsBigCSixteen")):
        match = re.search(r"\\newcommand\{\\" + macro + r"\}\{([\d,]+)\\xspace\}", study)
        if not match:
            raise ValueError(f"Missing frozen serving rate: {macro}")
        number(prefix, 1000 / int(match.group(1).replace(",", "")))

    aliases = {
        "rvOverlapExpert": "rvThinkAugOverlap", "rvOverlapNv": "rvThinkNvOverlap",
        "rvExpertRescues": "rvAugRescues", "rvSeedSpreadR": "rvSeedRecallSpread",
        "rvExpertFreshGains": "rvFreshAugAGains", "rvExpertFreshLosses": "rvFreshAugALosses",
        "rvExpertBenchGains": "rvBenchAugAGains", "rvExpertBenchLosses": "rvBenchAugALosses",
        "rvBaseBenchFmr": "rvBaseFmr", "rvBaseFreshFmr": "rvFreshBaseFmr",
        "rvFallbackBenchWork": "rvBenchFallbackWork", "rvFallbackFreshWork": "rvFreshFallbackWork",
        "rvFallbackBenchRate": "rvBenchFallbackRate", "rvFallbackFreshRate": "rvFreshFallbackRate",
        "rvFallbackBenchHours": "rvBenchFallbackHours", "rvFallbackFreshHours": "rvFreshFallbackHours",
        "rvLatencyBenchWork": "rvBenchFallbackLatencyWork", "rvLatencyFreshWork": "rvFreshFallbackLatencyWork",
        "rvThinkNewSpurious": "rvBenchThinkNewSm", "rvThinkRemovedSpurious": "rvBenchThinkRemovedSm",
    }
    values.update({alias: values[source] for alias, source in aliases.items()})

    lines = ["% Generated by gen_review_values.py; internal revision, 12 November 2026.",
             "% Inputs: data/review_diagnostics.json, data/replay_inputs.json, data/study_values.tex.",
             "% Paired intervals are archived results, not recomputed here; timing values are arithmetic proxies."]
    lines.extend(rf"\newcommand{{\{name}}}{{{value}\xspace}}" for name, value in values.items())
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify generated values without writing")
    args = parser.parse_args()
    rendered = generate()
    if args.check:
        if not OUT.exists() or OUT.read_text() != rendered:
            raise SystemExit("review_values.tex differs from verified diagnostics")
        print("review_values.tex matches the verified diagnostics")
    else:
        OUT.write_text(rendered)
        print("Wrote data/review_values.tex")


if __name__ == "__main__":
    main()
