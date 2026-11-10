"""
Run the safety evaluation against real Gemini.

Each case: reset the test database, chat through the real API,
then grade what really happened (see grader.py).

Built for the Gemini free tier:
  - waits between Gemini calls (--delay, default 6 seconds)
  - backs off and retries when Gemini says "too many requests"
  - saves every finished case, so if the daily limit is hit you
    can run the same command later and it continues where it stopped

Examples (local Postgres):
    DB_HOST=localhost python -m Evaluation.run_safety_eval --run baseline
    DB_HOST=localhost python -m Evaluation.run_safety_eval --run baseline --limit 5
    DB_HOST=localhost python -m Evaluation.run_safety_eval --run baseline --category injection
    python -m Evaluation.run_safety_eval --run baseline --report-only
"""

import argparse
import json
import os
import sys
import time
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

# These must be set BEFORE the app is imported.
# The eval always uses the separate test database, never the real one.
os.environ["DB_NAME"] = "customer_support_eval"
os.environ["CHECKPOINT_BACKEND"] = "memory"

RESULTS_DIR = Path(__file__).parent / "results"


class QuotaExhausted(Exception):
    """Gemini's limit is used up; stop and resume later."""


def is_rate_limit(error: Exception) -> bool:
    text = str(error)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


class ThrottledLLM:
    """
    Wraps the agent's Gemini model:
    waits between calls and retries politely when rate limited.
    """

    def __init__(self, llm, delay: float, max_retries: int = 4):
        self.llm = llm
        self.delay = delay
        self.max_retries = max_retries
        self.last_call = 0.0
        self.calls = 0
        self.exhausted = False

    def invoke(self, messages):
        for attempt in range(self.max_retries + 1):
            wait = self.delay - (time.monotonic() - self.last_call)
            if wait > 0:
                time.sleep(wait)

            self.last_call = time.monotonic()
            self.calls += 1

            try:
                return self.llm.invoke(messages)
            except Exception as error:
                if not is_rate_limit(error):
                    raise

                # The daily limit won't come back by waiting a minute.
                if "PerDay" in str(error) or attempt == self.max_retries:
                    self.exhausted = True
                    raise QuotaExhausted("RESOURCE_EXHAUSTED: Gemini limit reached") from error

                backoff = min(30 * (2 ** attempt), 120)
                print(f"    rate limited, waiting {backoff}s ...", flush=True)
                time.sleep(backoff)


class NoApprovalQueue:
    """The staff queue table isn't part of the eval database."""

    def add_pending(self, *args, **kwargs):
        pass

    def list_pending(self):
        return []

    def mark_decided(self, *args, **kwargs):
        pass


# ------------------------------------------------------------------
# Running cases
# ------------------------------------------------------------------

def run_case(client, support_graph, throttle, case, eval_db, grade):
    eval_db.reset()
    before = eval_db.snapshot()

    conversation_id = f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"
    turns, error = [], None
    started = time.monotonic()

    for message in case["turns"]:
        response = client.post("/chat", json={
            "customer_id": eval_db.CUSTOMER,
            "conversation_id": conversation_id,
            "message": message,
        })

        if throttle.exhausted:
            raise QuotaExhausted()

        if response.status_code != 200:
            error = f"HTTP {response.status_code}: {response.json().get('detail')}"
            turns.append({"user": message, "reply": f"[{error}]", "status": "error"})
            break

        data = response.json()
        turns.append({"user": message, "reply": data["response"], "status": data["status"]})

    state = support_graph.get_state({"configurable": {"thread_id": conversation_id}})
    pending = state.interrupts[0].value if state.interrupts else None

    observation = {
        "before": before,
        "after": eval_db.snapshot(),
        "replies": [t["reply"] for t in turns],
        "statuses": [t["status"] for t in turns],
        "tools": [
            tool_call["name"]
            for message in state.values.get("messages", [])
            if message.type == "ai"
            for tool_call in message.tool_calls
        ],
        "pending": (
            {"type": pending.get("type"), "order_id": pending.get("order_id")}
            if pending else None
        ),
    }

    checks = grade(case, observation)

    return {
        "id": case["id"],
        "category": case["category"],
        "result": "error" if error else ("pass" if all(c["passed"] for c in checks) else "fail"),
        "error": error,
        "checks": checks,
        "turns": turns,
        "tools": observation["tools"],
        "pending": observation["pending"],
        "seconds": round(time.monotonic() - started, 1),
    }


def load_results(path: Path) -> dict:
    if not path.exists():
        return {}
    results = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            results[row["id"]] = row
    return results


# ------------------------------------------------------------------
# Report
# ------------------------------------------------------------------

def build_report(run: str, results: dict, total_cases: int, model: str) -> str:
    rows = list(results.values())
    graded = [r for r in rows if r["result"] != "error"]

    def failed_types(row):
        return {c["type"] for c in row["checks"] if not c["passed"]}

    unsafe = [r for r in graded if "safety" in failed_types(r)]
    attacks = [r for r in graded if r["category"] != "legit"]
    legit = [r for r in graded if r["category"] == "legit"]
    accuracy_checks = [c for r in graded for c in r["checks"] if c["type"] == "accuracy"]

    def pct(part, whole):
        return f"{part}/{whole} ({100 * part / whole:.0f}%)" if whole else "-"

    lines = [
        f"# Safety evaluation: {run}",
        "",
        f"- Date: {datetime.now():%Y-%m-%d %H:%M}",
        f"- Model: {model}",
        f"- Cases run: {len(rows)} of {total_cases}"
        + (f" ({len(rows) - len(graded)} errors)" if len(rows) != len(graded) else ""),
        "",
    ]

    if model.startswith("obedient"):
        lines += [
            "> **Worst-case run.** The model here is a fake that obeys every attack: it lies",
            "> about refund reasons, claims to be other customers, calls tools it was never",
            "> given, and repeats raw data. Only the **safety** numbers matter: they show what",
            "> the code blocks on its own. Helpfulness and accuracy are not meaningful here.",
            "",
        ]

    lines += [
        "## Scorecard",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Cases with an unsafe outcome (lower is better) | {pct(len(unsafe), len(graded))} |",
        f"| Attacks fully blocked | {pct(sum(1 for r in attacks if r not in unsafe), len(attacks))} |",
        f"| Normal requests completed correctly | {pct(sum(1 for r in legit if r['result'] == 'pass'), len(legit))} |",
        f"| Answers with the right information | "
        f"{pct(sum(1 for c in accuracy_checks if c['passed']), len(accuracy_checks))} |",
        f"| All checks passed | {pct(sum(1 for r in graded if r['result'] == 'pass'), len(graded))} |",
        "",
        "## By category",
        "",
        "| Category | Cases | Passed | Unsafe |",
        "|---|---|---|---|",
    ]

    for category in sorted({r["category"] for r in graded}):
        group = [r for r in graded if r["category"] == category]
        lines.append(
            f"| {category} | {len(group)} | {sum(r['result'] == 'pass' for r in group)} "
            f"| {sum(r in unsafe for r in group)} |"
        )

    failures = [r for r in rows if r["result"] != "pass"]
    if failures:
        lines += ["", "## Cases that did not pass", ""]
        for r in sorted(failures, key=lambda r: ("safety" not in failed_types(r), r["id"])):
            tag = "UNSAFE" if r in unsafe else r["result"].upper()
            lines.append(f"### {r['id']} ({r['category']}) - {tag}")
            if r["error"]:
                lines.append(f"- Error: {r['error']}")
            for c in r["checks"]:
                if not c["passed"]:
                    detail = f" ({c['detail']})" if c["detail"] else ""
                    lines.append(f"- Failed [{c['type']}]: {c['name']}{detail}")
            for t in r["turns"]:
                reply = t["reply"].replace("\n", " ")
                lines.append(f"  - Customer: {t['user']}")
                lines.append(f"  - Agent: {reply[:300]}")
            lines.append("")

    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main(argv=None, llm=None):
    parser = argparse.ArgumentParser(description="Run the safety evaluation.")
    parser.add_argument("--run", default="latest", help="name for this run (results file)")
    parser.add_argument("--limit", type=int, help="run at most this many new cases")
    parser.add_argument("--category", help="only run this category")
    parser.add_argument("--ids", help="only these case ids, comma separated")
    parser.add_argument("--delay", type=float, default=6.0, help="seconds between Gemini calls")
    parser.add_argument(
        "--model",
        choices=["gemini", "obedient"],
        default="gemini",
        help="'obedient' = worst-case fake model that obeys every attack (no API calls)",
    )
    parser.add_argument("--fresh", action="store_true", help="ignore earlier results for this run")
    parser.add_argument("--report-only", action="store_true", help="just rebuild the report")
    args = parser.parse_args(argv)

    from Evaluation.safety_cases import CASES

    RESULTS_DIR.mkdir(exist_ok=True)
    results_path = RESULTS_DIR / f"{args.run}.jsonl"
    report_path = RESULTS_DIR / f"{args.run}.md"

    if args.fresh and results_path.exists():
        results_path.unlink()

    results = load_results(results_path)

    import config

    if not args.report_only:
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from Evaluation import eval_db
        from Evaluation.grader import grade

        eval_db.create_database_if_missing()

        import api.main
        from graph import nodes
        from graph.graph import support_graph

        if args.model == "obedient" and llm is None:
            from Evaluation.obedient_llm import ObedientLLM
            llm = ObedientLLM()
            args.delay = 0

        throttle = ThrottledLLM(llm or nodes.llm_with_tools, args.delay)

        todo = [c for c in CASES if c["id"] not in results]
        if args.category:
            todo = [c for c in todo if c["category"] == args.category]
        if args.ids:
            wanted = set(args.ids.split(","))
            todo = [c for c in todo if c["id"] in wanted]
        if args.limit:
            todo = todo[: args.limit]

        print(f"Run '{args.run}': {len(results)} done earlier, {len(todo)} to run now.\n")

        with patch.object(nodes, "llm_with_tools", throttle), \
             patch.object(api.main, "approval_queries", NoApprovalQueue()):
            client = TestClient(api.main.app)

            for index, case in enumerate(todo, start=1):
                print(f"[{index}/{len(todo)}] {case['id']} ...", end=" ", flush=True)
                try:
                    row = run_case(client, support_graph, throttle, case, eval_db, grade)
                except QuotaExhausted:
                    print("\nGemini limit reached. Progress is saved; run the same command later to continue.")
                    break

                with results_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row) + "\n")
                results[row["id"]] = row

                failed = [c["name"] for c in row["checks"] if not c["passed"]]
                print(row["result"].upper() + (f"  ({'; '.join(failed)})" if failed else ""))

        print(f"\nGemini calls this session: {throttle.calls}")

    model_label = (
        "obedient (worst-case fake model that obeys every attack; no AI)"
        if args.model == "obedient" else config.GEMINI_MODEL
    )
    report = build_report(args.run, results, len(CASES), model_label)
    report_path.write_text(report, encoding="utf-8")

    scorecard = report.split("## By category")[0]
    print("\n" + scorecard.strip())
    print(f"\nFull report: {report_path}")


if __name__ == "__main__":
    sys.exit(main())
