"""Run with:  python -m synth.generate

Reads train.json, findings.json, settings.json and notes_text.jsonl, and writes
  data/clean/   the BOM and ERP files before noise
  data/raw/     the three client files
  data/truth/   what was changed, what the notes state, what is planted, the verdicts
"""
import csv
import json
import random
import sys
from pathlib import Path

from . import noise
from .clean import BOM_COLUMNS, ERP_COLUMNS, NOTE_FIELDS, build_bom, build_erp, build_model, build_note_facts, note_rows

HERE = Path(__file__).parent
VERDICT_ORDER = ["specific", "reusable", "reused", "blocked"]   # the last one that applies wins


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def load_texts():
    path = HERE / "notes_text.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return {note["note_id"]: note["text"] for note in map(json.loads, lines)}


def build_clean(train, findings, settings):
    """Part 2: the clean model, the clean rows and the note facts."""
    seed = settings["seed"]
    model = build_model(train, findings, random.Random(f"{seed} model"))
    bom = build_bom(train, model)
    erp = build_erp(model, bom)
    facts = build_note_facts(findings, model, settings, random.Random(f"{seed} notes"))
    return model, bom, erp, facts


def write_csv(path, rows, columns, delimiter=","):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, columns, delimiter=delimiter, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


# --- the ground truth tables -------------------------------------------------

def relations_from(facts):
    return [{"note_id": f["note_id"], "relation": f["relation"], "ref_a_true": f["ref_a"], "ref_b_true": f["ref_b"],
             "ref_a_written": f["written_a"], "ref_b_written": f["written_b"],
             "ref_a_in_field": "yes" if f["in_field"] else "no", "option": f["option"],
             "overridden_by": f["overridden_by"]}
            for f in facts if f["relation"]]


def findings_from(findings, model, facts):
    """One row per planted finding, with the differing lines and the cost gap worked out."""
    cost = lambda ref: sum(q * model["parts"][c]["cost"] for c, q in model["designs"][ref]["components"].items())
    variants = lambda ref: " ".join(sorted(v for (v, _, _), used in model["use"].items() if used == ref))
    rows = []
    for f in findings["findings"]:
        b = f.get("b") or f.get("part")
        lines, gap = "", ""
        if f["b" if "b" in f else "a"] in model["designs"] and "b" in f and f["a"] in model["designs"]:
            one, two = model["designs"][f["a"]]["components"], model["designs"][b]["components"]
            lines = "; ".join(f"{c}: {one.get(c, 'absent')} -> {two.get(c, 'absent')}"
                              for c in sorted(set(one) | set(two)) if one.get(c) != two.get(c))
            if f["kind"].startswith("near_pair"):
                gap = f"{cost(b) - cost(f['a']):.2f}"
        note_ids = " ".join(n["note_id"] for n in facts if n["relation"] and any(
            n["relation"] == note["relation"] and [n["ref_a"], n["ref_b"]] == (note["refs"] + [""])[:2]
            for note in f.get("notes", [])))
        rows.append({"finding_id": f["id"], "kind": f["kind"],
                     "ref_a": f["a"], "variants_a": variants(f["a"]), "ref_b": b, "variants_b": variants(b),
                     "differing_lines": lines, "note_ids": note_ids, "cost_gap_eur": gap, "expect": f["expect"]})
    return rows


def verdicts_from(findings, model):
    """One row per sub-assembly design.

    Default: reused if it is in two variants or more, specific otherwise. Then the
    verdicts written in findings.json apply, the strongest one winning.
    """
    rows = []
    for ref in model["designs"]:
        variants = sorted(v for (v, _, _), used in model["use"].items() if used == ref)
        default = "reused" if len(variants) >= 2 else "specific"
        entries = [f for f in findings["findings"] if ref in f.get("verdicts", {})]
        strongest = lambda i: max([default] + [f["verdicts"][ref][i] for f in entries], key=VERDICT_ORDER.index)
        rows.append({"subassembly": ref, "variants": " ".join(variants), "verdict_bom_only": strongest(0),
                     "verdict_with_notes": strongest(1), "finding_ids": " ".join(f["id"] for f in entries)})
    return rows


# --- main --------------------------------------------------------------------

def main(root="."):
    root = Path(root)
    train, findings, settings = load("train.json"), load("findings.json"), load("settings.json")
    rates, rng = settings["noise"], random.Random(f"{settings['seed']} noise")

    # part 2: clean
    model, bom, erp, facts = build_clean(train, findings, settings)
    texts = load_texts()
    missing = [f["note_id"] for f in facts if f["note_id"] not in texts]
    if missing:
        sys.exit(f"{len(missing)} notes have no text. Run: python -m synth.write_note_texts")
    write_csv(root / "data/clean/plm_bom_export.csv", bom, BOM_COLUMNS)
    write_csv(root / "data/clean/erp_items.csv", erp, ERP_COLUMNS, delimiter=";")

    # part 3: noise, in the order of the plan
    skip = noise.protected(findings, bom)
    names = {**model["parts"], **model["designs"]}
    w = rates["v1_weight"]
    changes = []
    changes += noise.reference_twins(bom, erp, rates["reference_twins"], skip, w, rng)
    changes += noise.repeated_lines(bom, rates["repeated_lines"], rates["repeated_lines_other_quantity"], skip, w, rng)
    changes += noise.mixed_units(bom, erp, rates["mixed_units"], skip, w, rng)
    changes += noise.language_switch(bom, erp, names, rates["language_switch"], w, rng)
    changes += noise.cost_conflicts(erp, rates["cost_conflicts"], rng)
    changes += noise.supplier_variants(erp, train["suppliers"], rng)
    changes += noise.missing_values(erp, rates["missing_values"], skip, train["suppliers"], rng)
    write_csv(root / "data/raw/plm_bom_export.csv", bom, BOM_COLUMNS)
    write_csv(root / "data/raw/erp_items.csv", erp, ERP_COLUMNS, delimiter=";")
    write_jsonl(root / "data/raw/technical_notes.jsonl", note_rows(facts, texts))

    # part 4: ground truth
    line = {noise.BOM: {r["_id"]: i for i, r in enumerate(bom, 1)}, noise.ERP: {r["_id"]: i for i, r in enumerate(erp, 1)}}
    for change in changes:
        change["raw_row"] = line[change["file"]][change["row_id"]]
    truth = root / "data/truth"
    write_csv(truth / "changes.csv", changes, ["file", "row_id", "raw_row", "field", "clean_value", "written_value", "kind"])
    write_csv(truth / "relations.csv", relations_from(facts), ["note_id", "relation", "ref_a_true", "ref_b_true",
              "ref_a_written", "ref_b_written", "ref_a_in_field", "option", "overridden_by"])
    write_csv(truth / "findings.csv", findings_from(findings, model, facts), ["finding_id", "kind", "ref_a", "variants_a",
              "ref_b", "variants_b", "differing_lines", "note_ids", "cost_gap_eur", "expect"])
    write_csv(truth / "verdicts.csv", verdicts_from(findings, model), ["subassembly", "variants", "verdict_bom_only",
              "verdict_with_notes", "finding_ids"])
    print(f"BOM {len(bom)} rows, ERP {len(erp)} rows, {len(facts)} notes, {len(changes)} changes -> {root / 'data'}")


if __name__ == "__main__":
    main()
