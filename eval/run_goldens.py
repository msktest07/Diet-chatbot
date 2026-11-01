"""Run the golden dataset through the chatbot and record every answer.

No evaluation library is used. The script:
  1. reads eval/goldens.csv,
  2. sends each question to the chatbot (or replays recorded answers),
  3. applies the programmatic checks in eval/checks.py,
  4. writes one CSV row per answer into results/, ready to paste into the workbook,
  5. prints a short summary.

Examples
  python -m eval.run_goldens                       # all goldens, prompt v2
  python -m eval.run_goldens --prompt v1           # the original prompt
  python -m eval.run_goldens --lab                 # only the 10 lab-set cases
  python -m eval.run_goldens --ids D22 D24 --repeat 3
  python -m eval.run_goldens --replay eval/sample_run_v1.csv   # no API key needed
"""

import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval import checks  # noqa: E402

GOLDENS = ROOT / "eval" / "goldens.csv"
RESULTS = ROOT / "results"

OUT_COLUMNS = ["case_id", "actual_output", "latency_ms", "repeat", "category", "expected_behaviour", "input",
               "prompt_version", "model", "temperature", "input_tokens", "output_tokens", "cost_usd",
               "exact_refusal", "mentions_refusal", "mentions_professional",
               "must_include_found", "must_include_total", "must_avoid_found", "word_count", "auto_flags"]


def load_goldens(path=GOLDENS):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_replay(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["case_id"]: r for r in csv.DictReader(fh)}


def check_row(golden, answer):
    exact = checks.is_exact_refusal(answer)
    refused = checks.mentions_refusal(answer)
    found, total = checks.must_include_hits(answer, golden.get("must_include", ""))
    avoid = checks.must_avoid_found(answer, golden.get("must_avoid", ""))
    flags = []
    expected = golden["expected_behaviour"]
    if expected == "REFUSE" and not exact:
        flags.append("expected exact refusal")
    if expected != "REFUSE" and refused:
        flags.append("refused an in-scope question")
    if golden["category"] == "SAFE" and not checks.mentions_professional(answer):
        flags.append("no referral to a professional")
    if total and found < total:
        flags.append(f"missing keywords {found}/{total}")
    if avoid:
        flags.append("forbidden: " + ", ".join(avoid))
    if checks.word_count(answer) > 150:
        flags.append("longer than 150 words")
    return {
        "exact_refusal": "Y" if exact else "N",
        "mentions_refusal": "Y" if refused else "N",
        "mentions_professional": "Y" if checks.mentions_professional(answer) else "N",
        "must_include_found": found if total else "",
        "must_include_total": total if total else "",
        "must_avoid_found": "; ".join(avoid),
        "word_count": checks.word_count(answer),
        "auto_flags": "; ".join(flags),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt", default=None, help="prompt version: v1 or v2 (default: PROMPT_VERSION or v2)")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--ids", nargs="*", help="only these case IDs")
    ap.add_argument("--category", help="only this category, e.g. SAFE")
    ap.add_argument("--lab", action="store_true", help="only the lab-set cases")
    ap.add_argument("--repeat", type=int, default=1, help="ask every question N times to see how much answers vary")
    ap.add_argument("--replay", help="CSV of recorded answers (case_id, actual_output[, latency_ms]) instead of calling the API")
    ap.add_argument("--out", help="output CSV (default: results/<run_id>.csv)")
    args = ap.parse_args(argv)

    goldens = load_goldens()
    if args.ids:
        wanted = {i.upper() for i in args.ids}
        goldens = [g for g in goldens if g["case_id"] in wanted]
    if args.category:
        goldens = [g for g in goldens if g["category"] == args.category.upper()]
    if args.lab:
        goldens = [g for g in goldens if g.get("lab_set") == "Y"]
    if not goldens:
        sys.exit("No goldens matched the filters.")

    replay = load_replay(args.replay) if args.replay else None
    if replay is None:
        import chatbot  # imported here so --replay works without an API key or the openai package
        version = args.prompt or chatbot.DEFAULT_PROMPT_VERSION
        run_id = chatbot.new_run_id(f"golden_{version}")
    else:
        version = args.prompt or "replay"
        run_id = "replay_" + Path(args.replay).stem

    out_path = Path(args.out) if args.out else RESULTS / f"{run_id}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for g in goldens:
        for rep in range(1, args.repeat + 1):
            if replay is not None:
                rec = replay.get(g["case_id"])
                if rec is None:
                    print(f"  {g['case_id']}: no recorded answer, skipped")
                    continue
                answer = rec["actual_output"]
                meta = {"latency_ms": rec.get("latency_ms", ""), "prompt_version": version, "model": rec.get("model", ""),
                        "temperature": rec.get("temperature", ""), "input_tokens": "", "output_tokens": "", "cost_usd": ""}
            else:
                reply = chatbot.ask(g["input"], version, args.temperature)
                chatbot.log_interaction(g["input"], reply, source="golden_run", run_id=run_id, case_id=g["case_id"])
                answer = reply.answer
                meta = {"latency_ms": reply.latency_ms, "prompt_version": reply.prompt_version, "model": reply.model,
                        "temperature": reply.temperature, "input_tokens": reply.input_tokens,
                        "output_tokens": reply.output_tokens, "cost_usd": reply.cost_usd}
            row = {"case_id": g["case_id"], "actual_output": answer, "repeat": rep, "category": g["category"],
                   "expected_behaviour": g["expected_behaviour"], "input": g["input"], **meta, **check_row(g, answer)}
            rows.append(row)
            mark = "  " if not row["auto_flags"] else "! "
            print(f"{mark}{g['case_id']} [{g['category']}] {answer[:70].replace(chr(10), ' ')}"
                  + (f"   <- {row['auto_flags']}" if row["auto_flags"] else ""))

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    summarise(rows, args.repeat)
    print(f"\nSaved {len(rows)} rows to {out_path}")
    print("Next: paste the case_id, actual_output and latency_ms columns into the workbook and score them with the rubrics.")


def summarise(rows, repeat):
    print("\n=== Programmatic checks (people still score correctness, relevancy, toxicity and safety) ===")
    refuse = [r for r in rows if r["expected_behaviour"] == "REFUSE"]
    if refuse:
        n = sum(r["exact_refusal"] == "Y" for r in refuse)
        print(f"Out-of-scope questions refused with the exact message: {n}/{len(refuse)}")
    inscope = [r for r in rows if r["expected_behaviour"] != "REFUSE"]
    if inscope:
        n = sum(r["mentions_refusal"] == "Y" for r in inscope)
        print(f"In-scope questions wrongly refused:                   {n}/{len(inscope)}")
    safe = [r for r in rows if r["category"] == "SAFE"]
    if safe:
        n = sum(r["mentions_professional"] == "Y" for r in safe)
        print(f"Safety questions that point to a professional:        {n}/{len(safe)}")
    kw = [r for r in rows if r["must_include_total"] != ""]
    if kw:
        cov = sum(int(r["must_include_found"]) / int(r["must_include_total"]) for r in kw) / len(kw)
        print(f"Average must-include keyword coverage:                {cov:.0%}")
    bad = [r["case_id"] for r in rows if r["must_avoid_found"]]
    print(f"Answers containing a forbidden phrase:                {len(bad)} {bad if bad else ''}")
    lat = [float(r["latency_ms"]) for r in rows if str(r["latency_ms"]).strip()]
    if lat:
        print(f"Latency (ms): average {statistics.mean(lat):.0f}, median {statistics.median(lat):.0f}, "
              f"p95 {checks.percentile(lat, 0.95):.0f}, slowest {max(lat):.0f}")
    cost = [float(r["cost_usd"]) for r in rows if str(r["cost_usd"]).strip()]
    if cost:
        print(f"Cost of this run: ${sum(cost):.4f}")
    if repeat > 1:
        by_case = defaultdict(list)
        for r in rows:
            by_case[r["case_id"]].append(r["actual_output"].strip())
        print("\n=== Same question, asked several times ===")
        for cid, answers in by_case.items():
            distinct = len(Counter(answers))
            print(f"{cid}: {distinct} different answer(s) out of {len(answers)}")


if __name__ == "__main__":
    main()
