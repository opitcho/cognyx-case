"""Run by hand, once:  python -m synth.write_note_texts

Asks an LLM (through OpenRouter) to write the text of each note from its facts,
checks each text, and saves them to synth/inputs/notes_text.jsonl. Normal generation
only reads that file, so it needs no API key and gives the same notes every time.

Needs OPENROUTER_API_KEY in the environment or in a .env file at the repo root.
"""
import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .generate import INPUTS, build_clean, load, load_texts

# anything shaped like a part reference: two capitals, an optional separator, then digits
# (the letters O and I are allowed among the digits because typos put them there)
REFERENCE_SHAPE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}[- ]?[0-9OI]{2,6}(?![A-Za-z0-9])")


def check_text(fact, text):
    """Problems with a note text; an empty list if it is fine.

    The references of the facts must be there exactly, and nothing else that
    looks like a reference may be there.
    """
    problems = []
    expected = {fact["written_a"], fact["written_b"]} - {""}
    must_appear = expected if not fact["in_field"] else {fact["written_b"]} - {""}
    for ref in sorted(must_appear):
        if ref not in text:
            problems.append(f"the text must contain {ref} exactly")
    for found in REFERENCE_SHAPE.findall(text):
        if found not in expected:
            problems.append(f"the text contains {found}, which looks like a part reference and is not in the facts")
    if not text.strip() or "\n" in text.strip():
        problems.append("the text must be one non-empty line")
    return problems


def ask(model, key, prompt, fact, problems):
    """One call to OpenRouter. Returns the note text."""
    given = {k: fact[k] for k in ["date", "language", "relation", "written_a", "part_a", "written_b", "part_b", "in_field", "option", "topic"]}
    user = json.dumps(given, ensure_ascii=False)
    if problems:
        user += "\n\nYour previous text was rejected: " + "; ".join(problems)
    body = {"model": model, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user}]}
    request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", json.dumps(body).encode(),
                                     {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)["choices"][0]["message"]["content"].strip()


def write_text(model, key, prompt, fact):
    """Ask until the text passes the check, three times at most."""
    problems = []
    for _ in range(3):
        text = ask(model, key, prompt, fact, problems)
        problems = check_text(fact, text)
        if not problems:
            return text
    raise ValueError(f"{fact['note_id']}: no valid text after 3 tries: {problems}")


def api_key():
    env = Path(".env")
    if "OPENROUTER_API_KEY" not in os.environ and env.exists():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            os.environ.setdefault(name.strip(), value.strip().strip('"'))
    return os.environ["OPENROUTER_API_KEY"]


def main():
    train, findings, settings = load("train.json"), load("findings.json"), load("settings.json")
    facts = build_clean(train, findings, settings)[3]
    prompt = (INPUTS / "notes_prompt.md").read_text(encoding="utf-8")

    # keep the texts already written that still match their facts
    texts = {f["note_id"]: load_texts().get(f["note_id"], "") for f in facts}
    todo = [f for f in facts if not texts[f["note_id"]] or check_text(f, texts[f["note_id"]])]
    print(f"{len(facts)} notes, {len(todo)} to write with {settings['notes_model']}")
    if todo:
        key = api_key()
        with ThreadPoolExecutor(8) as pool:
            for fact, text in zip(todo, pool.map(lambda f: write_text(settings["notes_model"], key, prompt, f), todo)):
                texts[fact["note_id"]] = text

    lines = [json.dumps({"note_id": f["note_id"], "text": texts[f["note_id"]]}, ensure_ascii=False) for f in facts]
    (INPUTS / "notes_text.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (INPUTS / "notes_facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("written: synth/inputs/notes_text.jsonl, and the facts they were written from: synth/inputs/notes_facts.json")


if __name__ == "__main__":
    main()
