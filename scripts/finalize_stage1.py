from __future__ import annotations

import argparse
import csv
import json

import numpy as np

from common import RESULTS, write_rows

REPORT = RESULTS / "SAMPLER_REPORT.md"
LEVELS = ("a", "b-easy", "b-hard", "c")
SAMPLERS = ("gibbs", "mh-local", "mh-uniform", "pcd", "pt", "qemcmc", "exact")
SEEDS = (0, 1, 2)


def validate_canonical_budget(tag, canonical_budget):
    if tag != "g3-v2-gpu":
        return
    if canonical_budget[:3] != (100, 1, 32):
        raise RuntimeError(
            "tag g3-v2-gpu requires updates=100, chains=1, proposal_steps=32; "
            f"found {canonical_budget[:3]}"
        )
    if canonical_budget[-2:] != ("gpu", 20):
        raise RuntimeError(
            "tag g3-v2-gpu requires backend=gpu and bit_width=20; "
            f"found backend={canonical_budget[-2]} bit_width={canonical_budget[-1]}"
        )


def markdown_table(rows, columns):
    header = "| " + " | ".join(columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, rule, *body])


def replace_generated_tables(summary_rows, causal_rows, tag):
    start = "<!-- GENERATED TABLES START -->"
    end = "<!-- GENERATED TABLES END -->"
    text = REPORT.read_text(encoding="utf-8")
    if start not in text or end not in text:
        raise RuntimeError(f"missing generated-table markers in {REPORT}")
    summary_columns = ["level", "sampler", "seed", "backend", "bit_width", "best_val_exact_nll", "heldout_joint_exact_nll", "macro_f1", "accuracy", "ece_15bin", "classification_nll"]
    causal_columns = [
        "level", "sampler", "seeds_complete", "gradient_error_initial_mean",
        "gradient_error_final_mean", "gradient_error_all_mean", "energy_iat_mean",
        "energy_ess_per_proposal_mean", "magnetization_iat_mean",
        "magnetization_ess_per_proposal_mean", "tv_mean", "kl_mean",
        "mode_coverage_mean", "train_nll_initial_mean", "train_nll_final_mean",
        "train_nll_final_std", "val_nll_best_mean", "val_nll_final_mean",
        "val_nll_final_std",
    ]
    generated = (
        f"{start}\n"
        f"### Generated final metrics (`{tag}`)\n\n{markdown_table(summary_rows, summary_columns)}\n\n"
        f"### Generated causal-chain and stability summaries (`{tag}`)\n\n{markdown_table(causal_rows, causal_columns)}\n"
        f"{end}"
    )
    before, remainder = text.split(start, 1)
    _, after = remainder.split(end, 1)
    REPORT.write_text(before + generated + after, encoding="utf-8")


def mean(run_rows, field):
    return float(np.mean([float(row[field]) for row in run_rows]))


def aggregate_histories(paths):
    runs = {}
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise RuntimeError(f"empty history: {path}")
        rows.sort(key=lambda row: int(row["update"]))
        key = (rows[0]["level"], rows[0]["sampler"], int(rows[0]["seed"]))
        if key in runs:
            raise RuntimeError(f"duplicate history for {key}")
        expected_updates = int(rows[0]["updates"])
        if len(rows) != expected_updates or int(rows[-1]["update"]) != expected_updates:
            raise RuntimeError(f"incomplete history for {key}: {len(rows)}/{expected_updates}")
        runs[key] = rows
    causal = []
    for level in LEVELS:
        for sampler in SAMPLERS:
            grouped = [runs[(level, sampler, seed)] for seed in SEEDS if (level, sampler, seed) in runs]
            if not grouped:
                continue
            final_train = [float(rows[-1]["train_exact_nll"]) for rows in grouped]
            final_val = [float(rows[-1]["val_exact_nll"]) for rows in grouped]
            causal.append({
                "level": level,
                "sampler": sampler,
                "seeds_complete": len(grouped),
                "gradient_error_initial_mean": float(np.mean([float(rows[0]["gradient_error"]) for rows in grouped])),
                "gradient_error_final_mean": float(np.mean([float(rows[-1]["gradient_error"]) for rows in grouped])),
                "gradient_error_all_mean": float(np.mean([mean(rows, "gradient_error") for rows in grouped])),
                "energy_iat_mean": float(np.mean([mean(rows, "energy_iat") for rows in grouped])),
                "energy_ess_per_proposal_mean": float(np.mean([mean(rows, "energy_ess_per_proposal") for rows in grouped])),
                "magnetization_iat_mean": float(np.mean([mean(rows, "magnetization_iat") for rows in grouped])),
                "magnetization_ess_per_proposal_mean": float(np.mean([mean(rows, "magnetization_ess_per_proposal") for rows in grouped])),
                "tv_mean": float(np.mean([mean(rows, "tv") for rows in grouped])),
                "kl_mean": float(np.mean([mean(rows, "kl_sample_exact") for rows in grouped])),
                "mode_coverage_mean": float(np.mean([mean(rows, "mode_coverage") for rows in grouped])),
                "train_nll_initial_mean": float(np.mean([float(rows[0]["train_exact_nll"]) for rows in grouped])),
                "train_nll_final_mean": float(np.mean(final_train)),
                "train_nll_final_std": float(np.std(final_train)),
                "val_nll_best_mean": float(np.mean([min(float(row["val_exact_nll"]) for row in rows) for rows in grouped])),
                "val_nll_final_mean": float(np.mean(final_val)),
                "val_nll_final_std": float(np.std(final_val)),
            })
    return causal, runs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="g3-v1")
    parser.add_argument("--allow-partial", action="store_true", help="Engineering preview only; never use for the final G3 report.")
    parser.add_argument("--validate-only", action="store_true", help="Validate completeness and metadata without writing report artifacts.")
    args = parser.parse_args()
    metadata = sorted(RESULTS.glob(f"stage1_*_{args.tag}_metadata.json"))
    if not metadata:
        raise RuntimeError(f"no completed Stage-1 metadata for tag {args.tag}")
    summary = []
    for path in metadata:
        item = json.loads(path.read_text(encoding="utf-8")); budget = item["budget"]; metrics = item["test_metrics"]
        if item.get("backend") != budget.get("backend"):
            raise RuntimeError(f"backend metadata mismatch in {path}")
        summary.append({**budget, "bit_width": item.get("bit_width"), "best_val_exact_nll": item["best_val_exact_nll"], "heldout_joint_exact_nll": metrics["heldout_joint_exact_nll"], "macro_f1": metrics["macro_f1"], "accuracy": metrics["accuracy"], "ece_15bin": metrics["ece_15bin"], "classification_nll": metrics["nll"]})
    required = {(level, sampler, seed) for level in LEVELS for sampler in SAMPLERS for seed in SEEDS}
    completed = {(row["level"], row["sampler"], int(row["seed"])) for row in summary if row["level"] in LEVELS}
    missing = sorted(required - completed)
    if missing and not args.allow_partial:
        raise RuntimeError(f"refusing incomplete final report: {len(completed)}/{len(required)} required runs; first missing={missing[0]}")
    required_rows = [row for row in summary if row["level"] in LEVELS]
    metadata_budgets = {(int(row["updates"]), int(row["chains"]), int(row["proposal_steps"]), row["tag"], row["backend"], int(row["bit_width"])) for row in required_rows}
    if len(metadata_budgets) != 1:
        raise RuntimeError(f"refusing mixed metadata budgets: {sorted(metadata_budgets)}")
    canonical_budget = next(iter(metadata_budgets))
    validate_canonical_budget(args.tag, canonical_budget)
    causal, history_runs = aggregate_histories(RESULTS.glob(f"stage1_*_{args.tag}_history.csv"))
    missing_histories = sorted(required - set(history_runs))
    if missing_histories and not args.allow_partial:
        raise RuntimeError(f"refusing incomplete histories: first missing={missing_histories[0]}")
    for key in required & set(history_runs):
        first = history_runs[key][0]
        history_budget = (int(first["updates"]), int(first["chains"]), int(first["proposal_steps"]), first["tag"], first["backend"], int(first["bit_width"]))
        if history_budget != canonical_budget:
            raise RuntimeError(f"history/metadata budget mismatch for {key}: history={history_budget}, canonical={canonical_budget}")
    if args.validate_only:
        print(
            f"Validated {len(required_rows)} metadata files and {len(history_runs)} histories "
            f"for tag {args.tag}; no files written."
        )
        return
    write_rows(RESULTS / f"stage1_summary_{args.tag}.csv", summary)
    write_rows(RESULTS / f"stage1_causal_summary_{args.tag}.csv", causal)
    replace_generated_tables(summary, causal, args.tag)
    print("Wrote complete causal/final CSVs and generated report tables. Interpretations and verdicts remain unfilled.")


if __name__ == "__main__":
    main()
