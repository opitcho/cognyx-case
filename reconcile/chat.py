"""Talk to the reconciliation agent in the terminal.

Run: uv run --env-file .env python -m reconcile.chat
"""

import argparse

from agent import DEFAULT_MODEL
from config import USAGE_LOG
from repl import repl

from reconcile.agent import reconciliation_agent

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenRouter model id")
    parser.add_argument("--max-cost", type=float, default=None, help="stop once the session has spent this many USD")
    cli = parser.parse_args()
    repl(reconciliation_agent(cli.model, max_cost=cli.max_cost), USAGE_LOG)
