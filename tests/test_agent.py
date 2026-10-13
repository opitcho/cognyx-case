"""The reconciliation agent, driven by a scripted model: it has the database tools and nothing else, and its
claims are written during the turn, without an approval."""

import json
import shutil

import pytest

from pipeline.claims import load
from reconcile.agent import SKILLS_DIR, reconciliation_agent
from reconcile.tools import Workbench


class Scripted:
    """A model that returns the given replies in order, in the shape the API returns them."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return self.replies.pop(0)


def reply(content="", **tool_call):
    message = {"role": "assistant", "content": content}
    if tool_call:
        name = tool_call.pop("tool")
        message["tool_calls"] = [{"id": f"call-{name}", "type": "function",
                                  "function": {"name": name, "arguments": json.dumps(tool_call)}}]
    return {"id": "gen-1", "provider": "test", "model": "test", "created": 1789748403,
            "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if tool_call else "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.0}}


@pytest.fixture
def bench(tmp_path, rules_log):
    shutil.copy(rules_log, tmp_path / "claims.jsonl")
    return Workbench(tmp_path / "pilot.db", tmp_path / "claims.jsonl", "data/raw", "test-model", "Oscar")


def supplier_proposal(bench) -> dict:
    return next(c for c in load(bench.log_path) if c["standing"] == "proposed" and c["subject"].startswith("supplier:"))


def test_the_skill_is_the_system_prompt_and_the_batch_agent_cannot_speak_for_a_person(bench):
    live = reconciliation_agent(client=Scripted(), workbench=bench)
    batch = reconciliation_agent(client=Scripted(), workbench=bench, live=False)
    assert "## Settling an open item" in live.messages[0]["content"] and "name: reconciliation" not in live.messages[0]["content"]
    assert "append_person_claim" in live.tool_map and "append_person_claim" not in batch.tool_map
    assert live.needs_approval == batch.needs_approval == set()


def test_the_agent_has_the_database_tools_and_this_repos_skills_and_nothing_else(bench):
    agent = reconciliation_agent(client=Scripted(), workbench=bench)
    schemas = {schema["function"]["name"] for schema in agent._tool_schemas()}
    assert schemas == {"describe_tables", "run_sql", "append_claim", "append_person_claim", "load_skill", "read_skill_file"}
    assert set(agent.skills) == {"reconciliation"} and agent.loaded_skills == ["reconciliation"]
    assert agent.skills["reconciliation"].path == SKILLS_DIR / "reconciliation"
    assert agent.load_skill("reconciliation").startswith("Skill 'reconciliation' is already loaded")
    with pytest.raises(ValueError):  # a skill's files only: not the raw data, the claim log or the database
        agent.read_skill_file("reconciliation", "../../data/claims.jsonl")


def test_the_agents_own_claim_is_written_during_the_turn(bench):
    before = len(load(bench.log_path))
    client = Scripted(reply(tool="append_claim", type="not_same_as", subject="ref:BL-330", object="ref:BL-338",
                            evidence=["bom:108", "bom:115"], reason="two bolt lengths"), reply("Done."))
    agent = reconciliation_agent(client=client, workbench=bench, live=False)
    agent.run_turn("Settle BL-330 / BL-338.")
    claims = load(bench.log_path)
    assert len(claims) == before + 1 and claims[-1]["made_by"] == "agent"
    assert "recorded and in force" in agent.messages[-2]["content"]  # the tool's reply, which the model reads


def test_a_persons_claim_is_written_during_the_turn_without_an_approval(bench):
    proposal = supplier_proposal(bench)
    before = len(load(bench.log_path))
    client = Scripted(reply(tool="append_person_claim", type="confirm", subject=f"claim:{proposal['id']}",
                            reason="one company"), reply("Recorded."))
    agent = reconciliation_agent(client=client, workbench=bench)
    agent.run_turn("Yes, they are the same supplier.")
    assert agent.pending_calls == [] and agent.messages[-1]["content"] == "Recorded."
    claims = load(bench.log_path)
    assert len(claims) == before + 1
    assert (claims[-1]["type"], claims[-1]["made_by"], claims[-1]["maker"]) == ("confirm", "person", "Oscar")
