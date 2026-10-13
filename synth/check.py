"""Run with:  python -m synth.check

Part 6 of the plan. Reads the files on disk (data/clean, data/raw, data/truth)
and checks them, so that it tests what was written and not what the generator
believes it wrote. Prints a report, saves it to data/truth/check_report.txt, and
exits with an error if a check fails.
"""
import csv
import hashlib
import json
import random
import sys
import tempfile
from collections import Counter
from itertools import combinations
from pathlib import Path

from . import generate
from .clean import BOM_COLUMNS, ERP_COLUMNS, NOTE_FIELDS
from .refs import distance, erp_form
from .write_note_texts import REFERENCE_SHAPE

BOM, ERP = "plm_bom_export.csv", "erp_items.csv"
CLONES = ("clone", "clone_dead_reference")


def read_csv(path, delimiter=","):
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file, delimiter=delimiter))


def result(name, expected, found, passed):
    return {"name": name, "expected": str(expected), "found": str(found), "passed": bool(passed)}


def replay(clean_rows, changes, file):
    """Apply the logged changes to the clean rows, in order. Should give the raw rows."""
    rows = [{**row, "_id": str(i), "_clean": dict(row)} for i, row in enumerate(clean_rows, 1)]
    for change in changes:
        if change["file"] != file:
            continue
        if change["field"] == "":  # a copied row, inserted right after its source
            base = change["row_id"].split("+")[0]
            at = next(i for i, r in enumerate(rows) if r["_id"] == base)
            rows.insert(at + 1, {**rows[at], "_id": change["row_id"], "_clean": dict(rows[at]["_clean"])})
        else:
            next(r for r in rows if r["_id"] == change["row_id"])[change["field"]] = change["written_value"]
    return rows


def contents(bom):
    """sub-assembly reference -> {component: quantity}, from clean BOM rows."""
    found = {}
    for row in bom:
        if row["level"] == "4":
            found.setdefault(row["parent_ref"], {})[row["child_ref"]] = row["quantity"]
    return found


def differing_lines(a, b):
    """A swap counts as one line; so does the same component in another quantity."""
    only_a, only_b = set(a) - set(b), set(b) - set(a)
    return max(len(only_a), len(only_b)) + sum(1 for c in set(a) & set(b) if a[c] != b[c])


# --- the files are what part 1 says ------------------------------------------

def check_formats(raw):
    bom_text = (raw / BOM).read_text(encoding="utf-8")
    erp_text = (raw / ERP).read_text(encoding="utf-8")
    bom, erp = read_csv(raw / BOM), read_csv(raw / ERP, ";")
    notes = [json.loads(line) for line in (raw / "technical_notes.jsonl").read_text(encoding="utf-8").splitlines()]
    results = [
        result("1a BOM columns", BOM_COLUMNS, bom_text.splitlines()[0].split(","), bom_text.splitlines()[0].split(",") == BOM_COLUMNS),
        result("1b ERP columns", ERP_COLUMNS, erp_text.splitlines()[0].split(";"), erp_text.splitlines()[0].split(";") == ERP_COLUMNS),
        result("1c note fields", NOTE_FIELDS, sorted({tuple(n) for n in notes}), all(list(n) == NOTE_FIELDS for n in notes)),
    ]
    bad = [r["quantity"] for r in bom if not r["quantity"].replace(".", "", 1).isdigit()]
    results.append(result("1d BOM quantities are numbers with a decimal point", "none bad", bad[:5] or "none bad", not bad))
    bad = [r["unit_cost_eur"] for r in erp if r["unit_cost_eur"] and not r["unit_cost_eur"].replace(",", "", 1).isdigit()]
    results.append(result("1e ERP prices are numbers with a decimal comma, or empty", "none bad", bad[:5] or "none bad", not bad))

    broken = 0
    for variant in sorted({r["variant_id"] for r in bom}):
        rows = [r for r in bom if r["variant_id"] == variant]
        children = {level: {r["child_ref"] for r in rows if r["level"] == level} for level in "23"}
        broken += sum(1 for r in rows if (r["level"] == "3" and r["parent_ref"] not in children["2"])
                      or (r["level"] == "4" and r["parent_ref"] not in children["3"]))
        broken += len({(r["cars"], r["speed_class_kmh"], r["interior"]) for r in rows}) != 1
    results.append(result("2 every parent exists one level up, in every variant", 0, broken, broken == 0))
    return results


# --- the ground truth matches the files --------------------------------------

def check_changes_explain_everything(clean, raw, changes):
    results = []
    for file, delimiter, columns in [(BOM, ",", BOM_COLUMNS), (ERP, ";", ERP_COLUMNS)]:
        replayed = [{c: r[c] for c in columns} for r in replay(read_csv(clean / file, delimiter), changes, file)]
        written = read_csv(raw / file, delimiter)
        differences = sum(a != b for a, b in zip(replayed, written)) + abs(len(replayed) - len(written))
        results.append(result(f"3 clean {file} + changes.csv = raw {file}", "0 rows differ", f"{differences} rows differ", differences == 0))

    true_refs = {r["child_ref"] for r in read_csv(clean / BOM) if r["level"] in "34"}
    twins = {(c["clean_value"], c["written_value"]) for c in changes if c["kind"] == "reference_twin" and c["field"]}
    collisions, ambiguous = [], []
    for true, written in twins:
        others = true_refs if "-" in true else {erp_form(r) for r in true_refs}
        if written in others:
            collisions.append(written)
        if any(distance(written, other) <= distance(written, true) for other in others if other != true):
            ambiguous.append(written)
    results.append(result("4a no mistyped reference equals a real reference", "none", collisions or "none", not collisions))
    results.append(result("4b every mistyped reference is closest to its own part", "none ambiguous", ambiguous or "none ambiguous", not ambiguous))
    return results


# --- the findings are really in the data -------------------------------------

def check_findings_are_in_clean_data(clean_bom, findings, settings):
    content = contents(clean_bom)
    system_of = {r["child_ref"]: r["parent_ref"] for r in clean_bom if r["level"] == "3"}
    description = {r["child_ref"]: r["description"] for r in clean_bom if r["level"] == "3"}

    # one sub-assembly reference must always have the same content
    signature = lambda ref: frozenset(content[ref].items())
    groups = {}  # identical content -> the references that have it
    for ref in content:
        groups.setdefault(signature(ref), set()).add(ref)
    group_of = {ref: frozenset(refs) for refs in groups.values() for ref in refs}

    planted_clones = set()
    for f in findings:
        if f["kind"] in CLONES:
            planted_clones.add(group_of[f["ref_a"]])
            ok = group_of[f["ref_a"]] == group_of[f["ref_b"]]
            planted_clones.add(group_of[f["ref_b"]]) if not ok else None
    found_clones = {refs for refs in set(group_of.values()) if len(refs) > 1}
    results = [result("5a identical sub-assemblies in the clean BOM = the planted clones",
                      sorted(map(sorted, planted_clones)), sorted(map(sorted, found_clones)), planted_clones == found_clones)]

    found_near = set()
    for one, two in combinations(set(group_of.values()), 2):
        a, b = sorted(one)[0], sorted(two)[0]
        if system_of[a] == system_of[b] and 1 <= differing_lines(content[a], content[b]) <= 3 \
                and len(set(content[a]) & set(content[b])) >= 4:
            found_near.add(frozenset([one, two]))
    planted_near = {frozenset([group_of[f["ref_a"]], group_of[f["ref_b"]]]) for f in findings if f["kind"].startswith("near_pair")}
    show = lambda pairs: sorted(sorted(sorted(g)[0] for g in pair) for pair in pairs)
    results.append(result("5b near pairs (1 to 3 lines apart, 4 shared components) in the clean BOM = the planted ones",
                          show(planted_near), show(found_near), planted_near == found_near))

    functional = [f for f in findings if f["kind"] == "functional_pair"]
    shared = [f["finding_id"] for f in functional if set(content[f["ref_a"]]) & set(content[f["ref_b"]])]
    results.append(result("6a functional pairs share no component", "none share", shared or "none share", not shared))
    lookalikes = [f for f in findings if f["kind"] == "lookalike_subassemblies"]
    bad = [f["finding_id"] for f in lookalikes if description[f["ref_a"]] != description[f["ref_b"]]
           or differing_lines(content[f["ref_a"]], content[f["ref_b"]]) < 4]
    results.append(result("6b look-alike sub-assemblies have the same name and 4 or more differing lines", "all", bad or "all", not bad))
    pairs = [f for f in findings if f["kind"] == "lookalike_references"]
    bad = [f["finding_id"] for f in pairs if distance(f["ref_a"], f["ref_b"]) != 1]
    results.append(result("6c look-alike references are exactly one character apart", "all", bad or "all", not bad))
    close = [(a, b) for a, b in combinations(sorted(set(content) | {c for d in content.values() for c in d}), 2)
             if distance(a, b) < 2 and not any({a, b} == {f["ref_a"], f["ref_b"]} for f in pairs)]
    results.append(result("6d no other two references are one character apart", "none", close or "none", not close))

    counts = Counter(f["kind"] for f in findings)
    short = {k: counts[k] for k, minimum in settings["minimum_findings"].items() if counts[k] < minimum}
    results.append(result("7a each kind of finding meets its minimum", settings["minimum_findings"], dict(counts), not short))

    in_v1 = {r["child_ref"] for r in clean_bom if r["variant_id"] == "V1"}
    v1_groups = {ref for own in in_v1 if own in group_of for ref in group_of[own]} | in_v1
    absent = sorted(k for k in counts if not any(f["kind"] == k and {f["ref_a"], f["ref_b"]} & v1_groups for f in findings))
    results.append(result("7b V1 has at least one finding of each kind", "all kinds", absent or "all kinds", not absent))
    return results


# --- the noise and the notes matter ------------------------------------------

def check_noise(clean, raw, changes, findings, verdicts, settings):
    rates = settings["noise"]
    clean_bom, clean_erp = read_csv(clean / BOM), read_csv(clean / ERP, ";")
    raw_bom, raw_erp = read_csv(raw / BOM), read_csv(raw / ERP, ";")
    results = []

    def amount(name, expected, found):
        results.append(result(f"8 amount of noise: {name}", f"about {expected:.0f}", found, abs(found - expected) <= max(1, 0.25 * expected)))

    parts = len({r["child_ref"] for r in clean_bom if r["level"] in "34"})
    items = len(clean_erp)
    kinds = lambda kind, file=None: [c for c in changes if c["kind"] == kind and (file is None or c["file"] == file)]
    amount("references with a mistyped twin", rates["reference_twins"] * parts,
           len({c["clean_value"] for c in kinds("reference_twin", BOM)}))
    repeated = [c for c in kinds("repeated_line") if c["field"] == ""]
    amount("repeated BOM lines", rates["repeated_lines"] * len(clean_bom), len(repeated))
    amount("repeated lines with another quantity", rates["repeated_lines_other_quantity"] * len(repeated),
           len([c for c in kinds("repeated_line") if c["field"] == "quantity"]))
    clean_ref = lambda c: (clean_bom[int(c["row_id"].split("+")[0]) - 1]["child_ref"] if c["file"] == BOM
                           else clean_erp[int(c["row_id"].split("+")[0]) - 1]["item_ref"].replace(" ", ""))
    amount("items with a unit change", rates["mixed_units"] * items, len({erp_form(clean_ref(c)) for c in kinds("mixed_unit")}))
    amount("BOM descriptions in French", rates["language_switch"] * len(clean_bom), len(kinds("language", BOM)))
    amount("ERP descriptions in English", rates["language_switch"] * items, len(kinds("language", ERP)))
    twin_rows = len({c["row_id"] for c in kinds("reference_twin", ERP)})
    amount("cost conflicts", min(rates["cost_conflicts"] * items, twin_rows), len(kinds("cost_conflict")))
    amount("missing supplier or price", rates["missing_values"] * 2 * len(raw_erp), len(kinds("missing_value")))

    spellings = Counter(r["supplier"] for r in raw_erp)
    declared = [s["spellings"] for s in generate.load("train.json")["suppliers"] if "spellings" in s]
    unused = [name for names in declared for name in names if not spellings[name]]
    results.append(result("8 two suppliers appear under three spellings each", "all 6 spellings used", unused or "all 6 spellings used", not unused))

    in_bom = [c for c in changes if c["file"] == BOM]
    v1 = sum(1 for c in in_bom if clean_bom[int(c["row_id"].split("+")[0]) - 1]["variant_id"] == "V1") / len(in_bom)
    results.append(result("8 share of BOM changes that fall in V1", "at least 40%", f"{v1:.0%}", v1 >= 0.40))

    # 9. clones that are no longer identical in the raw BOM
    replayed = [r for r in replay(clean_bom, changes, BOM) if "+" not in r["_id"] and r["level"] == "4"]
    touched = {c["row_id"]: set() for c in changes}
    for c in changes:
        touched[c["row_id"]].add(c["kind"])

    def raw_versions(ref):  # the content of a sub-assembly as written, one per variant
        rows = [r for r in replayed if r["_clean"]["parent_ref"] == ref]
        return {v: frozenset((r["child_ref"], r["quantity"], r["unit"]) for r in rows if r["variant_id"] == v)
                for v in {r["variant_id"] for r in rows}}

    broken = {"reference_twin": [], "mixed_unit": []}
    for f in findings:
        if f["kind"] in CLONES:
            a, b = raw_versions(f["ref_a"]), raw_versions(f["ref_b"])
            if not set(a.values()) & set(b.values()):
                rows = [r for r in replayed if r["_clean"]["parent_ref"] in (f["ref_a"], f["ref_b"])]
                for kind in broken:
                    if any(kind in touched.get(r["_id"], ()) for r in rows):
                        broken[kind].append(f["finding_id"])
    results.append(result("9a clones not identical in the raw BOM because of a mistyped reference", "at least 2", broken["reference_twin"], len(broken["reference_twin"]) >= 2))
    results.append(result("9b clones not identical in the raw BOM because of a unit", "at least 2", broken["mixed_unit"], len(broken["mixed_unit"]) >= 2))

    # V1: a price for every component, looked up the way the pipeline will have to
    prices = {r["item_ref"]: r["unit_cost_eur"] for r in raw_erp}
    unpriced = sorted({r["child_ref"] for r in raw_bom if r["variant_id"] == "V1" and r["level"] == "4"
                       and not prices.get(erp_form(r["child_ref"]))})
    results.append(result("7c every V1 component has a price in the raw ERP file", "none without", unpriced or "none without", not unpriced))

    # 10. the notes change verdicts
    changed = [v["subassembly"] for v in verdicts if v["verdict_bom_only"] != v["verdict_with_notes"]]
    minimum = settings["minimum_verdicts_changed_by_notes"]
    results.append(result("10a designs whose verdict differs with and without the notes", f"at least {minimum}", f"{len(changed)}: {changed}", len(changed) >= minimum))
    return results


def check_notes(raw, clean_bom, relations, verdicts):
    notes = [json.loads(line) for line in (raw / "technical_notes.jsonl").read_text(encoding="utf-8").splitlines()]
    true_refs = {r["child_ref"] for r in clean_bom if r["level"] in "34"}
    by_note = {}
    for relation in relations:
        by_note.setdefault(relation["note_id"], []).append(relation)

    problems = []
    for note in notes:
        found = set(REFERENCE_SHAPE.findall(note["text"])) | ({note["reference"]} - {""})
        if note["note_id"] in by_note:
            for relation in by_note[note["note_id"]]:
                expected = {relation["ref_a_written"], relation["ref_b_written"]} - {""}
                if found != expected:
                    problems.append(f"{note['note_id']}: has {sorted(found)}, facts say {sorted(expected)}")
        elif not found <= true_refs:
            problems.append(f"{note['note_id']}: plain note mentions {sorted(found - true_refs)}, not a real reference")
    results = [result("11a every note contains the references of its facts and no others", "no problem", problems[:5] or "no problem", not problems)]

    ambiguous = []
    for relation in relations:
        for side in "ab":
            true, written = relation[f"ref_{side}_true"], relation[f"ref_{side}_written"]
            if written != true and any(distance(written, other) <= distance(written, true) for other in true_refs - {true}):
                ambiguous.append(written)
    mistyped = sum(1 for r in relations if (r["ref_a_true"], r["ref_b_true"]) != (r["ref_a_written"], r["ref_b_written"]))
    results.append(result("11b every mistyped reference in a note is closest to its own part", "none ambiguous", ambiguous or "none ambiguous", not ambiguous))
    results.append(result("11c notes: total, with a relation, with a mistyped reference, reference only in the text", "about 80, 30, 7, 14",
                          [len(notes), len(relations), mistyped, sum(1 for r in relations if r["ref_a_in_field"] == "no")],
                          70 <= len(notes) <= 90 and 24 <= len(relations) <= 36))

    # 10b. the verdicts agree with the notes: a design is blocked exactly when it is,
    # or contains, a part that a note (not overridden) calls obsolete or superseded
    dead = {r["ref_a_true"] for r in relations if r["relation"] in ("obsolete", "superseded_by") and not r["overridden_by"]}
    content = contents(clean_bom)
    should = {ref for ref in content if ref in dead or set(content[ref]) & dead}
    blocked = {v["subassembly"] for v in verdicts if v["verdict_with_notes"] == "blocked"}
    results.append(result("10b blocked designs = designs that are or contain an obsolete or superseded part", sorted(should), sorted(blocked), should == blocked))
    return results


def check_repeatable(root):
    """Generate again into a temporary folder and compare every file."""
    digest = lambda folder: {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "check_report.txt"}
    with tempfile.TemporaryDirectory() as again:
        generate.main(again)
        same = digest(Path(again) / "data") == {k: v for k, v in digest(root / "data").items() if not k.startswith("example_sources")}
    return [result("12 a second run gives identical files", "identical", "identical" if same else "different", same)]


def main(root="."):
    root = Path(root)
    clean, raw, truth = root / "data/clean", root / "data/raw", root / "data/truth"
    settings = generate.load("settings.json")
    changes, relations = read_csv(truth / "changes.csv"), read_csv(truth / "relations.csv")
    findings, verdicts = read_csv(truth / "findings.csv"), read_csv(truth / "verdicts.csv")
    clean_bom = read_csv(clean / BOM)

    results = check_formats(raw)
    results += check_changes_explain_everything(clean, raw, changes)
    results += check_findings_are_in_clean_data(clean_bom, findings, settings)
    results += check_noise(clean, raw, changes, findings, verdicts, settings)
    results += check_notes(raw, clean_bom, relations, verdicts)
    results += check_repeatable(root)

    lines = []
    for r in sorted(results, key=lambda r: (int("".join(ch for ch in r["name"].split()[0] if ch.isdigit())), r["name"])):
        lines += [f"[{'PASS' if r['passed'] else 'FAIL'}] {r['name']}", f"       expected: {r['expected']}", f"       found:    {r['found']}"]
    failed = [r for r in results if not r["passed"]]
    lines += ["", f"{len(results) - len(failed)} of {len(results)} checks passed", "", "--- read-through: 10 random notes ---"]
    rng = random.Random(0)
    notes = (raw / "technical_notes.jsonl").read_text(encoding="utf-8").splitlines()
    lines += rng.sample(notes, 10) + ["", "--- read-through: 10 random changes ---"]
    lines += [f"{c['file']} row {c['raw_row']} {c['field'] or '(row added)'}: {c['clean_value']!r} -> {c['written_value']!r}  [{c['kind']}]"
              for c in rng.sample(changes, 10)]
    report = "\n".join(lines) + "\n"
    (truth / "check_report.txt").write_text(report, encoding="utf-8")
    print(report)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
