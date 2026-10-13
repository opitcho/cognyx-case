"""The reconciliation agent: the jean-code Agent with the four tools of `tools.py` and the skills of this repo."""

import getpass
import os
from pathlib import Path

import skills
from agent import DEFAULT_MODEL, Agent

from reconcile.tools import Workbench

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"  # this repo's skills, not the ones of jean-code
SKILL = "reconciliation"  # in the system prompt from the start


def reconciliation_agent(model: str = DEFAULT_MODEL, reasoning: str | None = "medium", budget=None, client=None,
                         live: bool = True, workbench: Workbench | None = None, max_tool_rounds: int = 100,
                         **kwargs) -> Agent:
    """An agent that reads the resolved database and appends claims.

    The four tools of the workbench are its only access to the data: it has no shell, no file tool and no web
    tool, so it cannot read or write `data/raw/`, the claim log or the database any other way. None of its calls
    waits for approval. With `live` it also gets `append_person_claim`, which writes a claim in the person's
    name. Without it (the batch run) what the agent cannot decide stays proposed.

    Its skills are the folders of `skills/` in this repo. The reconciliation skill's text is the system prompt,
    so a fresh agent needs no call to load it. Any other skill is listed there and loaded with `load_skill`.

    A turn may take up to `max_tool_rounds` rounds of tool calls. An open item with mixed evidence takes more
    than the framework's default of 10, and a turn cut off there leaves no claim. The budget is what limits cost.

    The paths are the ones under the directory it is started from, unless a `workbench` is given.
    """
    workbench = workbench or Workbench(agent_name=model, person_name=os.environ.get("RECONCILE_PERSON") or getpass.getuser())
    tools = {"describe_tables": workbench.describe_tables, "run_sql": workbench.run_sql,
             "append_claim": workbench.append_claim}
    if live:
        tools["append_person_claim"] = workbench.append_person_claim
    agent = Agent(model, system_prompt=skills.instructions(skills.discover_skills(SKILLS_DIR)[SKILL]), tools=tools,
                  skills_dir=SKILLS_DIR, reasoning=reasoning, budget=budget, client=client,
                  max_tool_rounds=max_tool_rounds, **kwargs)
    agent.loaded_skills.append(SKILL)
    return agent
