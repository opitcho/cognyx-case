"""The batch run: the agent works through the open items, one item per turn, each with a fresh conversation.

Its claims are applied at once. What it cannot decide stays proposed, for a person. The run stops when the queue
has nothing left that it has not tried, or when the budget is spent.

Run: uv run --env-file .env python -m reconcile.batch --max-cost 2
"""

import argparse
import json
import sqlite3

from agent import DEFAULT_MODEL
from usage import Budget

from reconcile.agent import reconciliation_agent
from reconcile.tools import Workbench, verdict_counts

# Notes first: they state the relations and name the references everything else is checked against.
ORDER = ("unread note", "near pair", "unresolved reference", "two quantities", "supplier names")


def open_items(workbench: Workbench) -> list[dict]:
    conn = workbench.connect()
    conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.execute("SELECT kind, detail, claim_id, source_rows FROM v_queue")]
    conn.close()
    return rows


def task(item: dict, workbench: Workbench) -> str:
    """What the agent is asked for one item."""
    if item["kind"] == "unread note":
        note = workbench.raw.note(item["source_rows"].split(":", 1)[1])
        return "Settle this open item: an unread note. Record what it states, then mark it reviewed.\n" + json.dumps(
            {k: note[k] for k in ("note_id", "date", "reference", "text")}, ensure_ascii=False)
    claim = f" (claim {item['claim_id']})" if item["claim_id"] else ""
    return f"Settle this open item of kind \"{item['kind']}\"{claim}: {item['detail']}\nRaw rows: {item['source_rows']}"


def run(max_cost: float, model: str = DEFAULT_MODEL, limit: int | None = None, kinds: tuple[str, ...] = ORDER) -> None:
    workbench = Workbench(agent_name=model)
    budget = Budget(max_cost, name="batch")
    print(f"start: {workbench.summary.line()}")
    tried: set[tuple] = set()
    done = 0
    while not budget.exhausted and (limit is None or done < limit):
        items = [i for i in open_items(workbench) if i["kind"] in kinds and (i["kind"], i["detail"]) not in tried]
        if not items:
            break
        item = min(items, key=lambda i: kinds.index(i["kind"]))  # the queue lists notes oldest first
        tried.add((item["kind"], item["detail"]))
        before = len(open_items(workbench))
        agent = reconciliation_agent(model, budget=budget.child(None, f"item-{done + 1}"), live=False, workbench=workbench)
        error = ""
        try:
            agent.run_turn(task(item, workbench))
        except Exception as e:  # one item failing must not stop the run
            error = f" ERROR {type(e).__name__}: {e}"
        done += 1
        left = len(open_items(workbench))
        print(f"{done:3} {item['kind']:20} {item['detail'][:70]:70} calls {len(agent.usage)} open {before} -> {left}"
              f" ${budget.spent:.3f}{error}", flush=True)
    stopped = "the budget is spent" if budget.exhausted else "nothing left to try"
    remaining = open_items(workbench)
    print(f"stopped: {stopped}. {done} items worked, {len(remaining)} still open, ${budget.spent:.4f} spent.")
    print(f"end:   {workbench.summary.line()}")
    print(f"verdicts: {verdict_counts(workbench.summary)}")
    for item in remaining[:30]:
        print(f"  open: {item['kind']}: {item['detail']}")
    if len(remaining) > 30:
        print(f"  ... and {len(remaining) - 30} more")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-cost", type=float, required=True, help="stop once the run has spent this many USD")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenRouter model id")
    parser.add_argument("--limit", type=int, default=None, help="work at most this many items")
    parser.add_argument("--kinds", nargs="+", default=list(ORDER), choices=ORDER, help="only these kinds of item")
    cli = parser.parse_args()
    run(cli.max_cost, cli.model, cli.limit, tuple(cli.kinds))
