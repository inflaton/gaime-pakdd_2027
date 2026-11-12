#!/usr/bin/env python3
"""Recompute overlap enrichment and unresolved link rates from aggregate counts."""

import argparse
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
INPUT = HERE / "data/review_diagnostics.json"
OUTPUT = HERE / "data/review_summary.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hypergeom_upper(population, successes, draws, observed):
    """Exact P[X >= observed], conditional on both fixed set sizes."""
    require(all(type(x) is int for x in (population, successes, draws, observed)), "Noninteger set size")
    require(0 <= successes <= population and 0 <= draws <= population, "Invalid rescue set size")
    lower, upper = max(0, draws - (population - successes)), min(successes, draws)
    if observed <= lower:
        return 1.0
    if observed > upper:
        return 0.0
    numerator = sum(math.comb(successes, x) * math.comb(population - successes, draws - x)
                    for x in range(observed, upper + 1))
    return numerator / math.comb(population, draws)


def validate_overlap(record):
    counts = record["counts"]
    require(sum(record["exact_membership"].values()) == record["union"], "Venn union mismatch")
    for arm, count in counts.items():
        require(sum(n for label, n in record["exact_membership"].items() if arm in label.split("+")) == count,
                "Venn marginal mismatch")
    enrichment = record["enrichment_vs_thinking"]
    population, thinking = enrichment["population"], enrichment["thinking_rescues"]
    require(thinking == counts["T1_think"], "Thinking rescue marginal mismatch")
    calculated = {}
    for arm, comparison in enrichment["comparisons"].items():
        draws, overlap = comparison["variant_rescues"], comparison["observed_overlap"]
        require(draws == counts[arm], "Variant rescue marginal mismatch")
        pair = f"T1_think+{arm}"
        require(overlap == record["pairwise_intersections"][pair], "Pairwise overlap mismatch")
        expected = thinking * draws / population
        p = hypergeom_upper(population, thinking, draws, overlap)
        require(math.isclose(expected, comparison["expected_overlap"], rel_tol=1e-12), "Expected overlap mismatch")
        require(math.isclose(p, comparison["p_upper"], rel_tol=1e-12), "Exact upper-tail probability mismatch")
        calculated[arm] = {"rescued": draws, "overlap_with_thinking": overlap,
                           "expected_overlap": expected, "one_sided_hypergeometric_p": p}
    return {"population": population, "thinking_rescues": thinking,
            "thinking_rescue_rate_pct": 100 * thinking / population, "comparisons": calculated}


def generate():
    bundle = json.loads(INPUT.read_text(encoding="utf-8"))
    result = {"method": "Exact one-sided hypergeometric enrichment conditional on fixed recovery-set sizes",
              "interpretation": "Exploratory uniform-overlap reference, not a causal model or independent confirmation",
              "benchmark": {}, "fresh": {}}
    for cohort in ("benchmark", "fresh"):
        section = bundle[cohort]
        result[cohort]["all_noncorrect_recoveries"] = validate_overlap(section["rescue_overlap"])
        result[cohort]["explicit_null_recoveries"] = validate_overlap(section["rescued_null_overlap"])
        for transition in section["transitions"].values():
            require(transition["newly_correct"] - transition["lost_correct"] == transition["net_correct"],
                    "Correct-selection transition mismatch")
            require(transition["new_spurious"] - transition["removed_spurious"] == transition["net_spurious"],
                    "Spurious-link transition mismatch")
    unresolved = bundle["fresh"]["unresolved_acceptance"]
    n = unresolved["n"]
    rates = {}
    for arm in ("T1", "T1_think", "T1_selective", "ZS", "R120"):
        record = unresolved["arms"][arm]
        rate = 100 * record["accepted"] / n
        require(math.isclose(rate, record["accepted_pct"], abs_tol=0.005), "Unresolved acceptance mismatch")
        rates[arm] = {"accepted": record["accepted"], "n_unresolved": n, "accepted_pct": rate}
    result["fresh"]["unresolved_acceptance"] = rates
    return json.dumps(result, indent=2, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the bundled summary without writing")
    args = parser.parse_args()
    # Boundary cases and a small distribution with an independently enumerable tail.
    require(hypergeom_upper(4, 2, 2, 1) == 5 / 6, "Small overlap distribution failed")
    require(hypergeom_upper(4, 2, 2, 0) == 1 and hypergeom_upper(4, 2, 2, 3) == 0,
            "Overlap probability boundary failed")
    rendered = generate()
    if args.check:
        require(OUTPUT.is_file() and OUTPUT.read_text(encoding="utf-8") == rendered, "Bundled review summary differs")
        print("Recovery enrichment, unresolved rates and transition totals match the aggregate inputs.")
    else:
        OUTPUT.write_text(rendered, encoding="utf-8")
        print("Wrote data/review_summary.json")


if __name__ == "__main__":
    main()
