"""Part 2 of the plan: build the clean data from train.json and findings.json.

Nothing here decides what is planted. The 15 hand-written positions come from
findings.json as they are; the 25 others are filled with random components.
"""
import datetime

from .refs import new_ref, typo

BOM_COLUMNS = ["variant_id", "cars", "speed_class_kmh", "interior", "level",
               "parent_ref", "child_ref", "description", "quantity", "unit"]
ERP_COLUMNS = ["item_ref", "description", "supplier", "unit_cost_eur", "price_unit"]
NOTE_FIELDS = ["note_id", "date", "reference", "text"]

PLAIN_TOPICS = ["inspection result", "torque check", "drawing update", "delivery delay",
                "non-conformity closed with no part change", "test report"]
TRAP_TOPICS = ["uses the word 'equivalent' but states no equivalence between parts",
               "uses the word 'obsolete' but says the part is NOT obsolete",
               "uses the word 'superseded' about a document, not about a part"]


def number(value):
    """2.0 -> '2', 2.4 -> '2.4'. Quantities are written the way a person would."""
    return str(int(value)) if float(value).is_integer() else f"{value:.5f}".rstrip("0")


# --- the model: parts, designs, and which variant uses which design ---------

def build_model(train, findings, rng):
    """Returns {'parts', 'designs', 'use'}.

    parts:   ref -> {en, fr, unit, supplier, cost}
    designs: sub-assembly ref -> {system, position, en, fr, components {ref: quantity}, hand}
    use:     (variant_id, system ref, position name) -> sub-assembly ref
    """
    parts, designs, use = {}, {}, {}
    taken = {system["ref"] for system in train["systems"]} | _hand_refs(findings)
    variants = [v["variant_id"] for v in train["variants"]]

    def add_part(ref, system, supplier=None):
        if ref in parts:
            return
        kind = train["kinds"][ref[:2]]
        size = rng.choice(kind["sizes"]) if "sizes" in kind else ""
        names = findings["parts"].get(ref) or {"en": f"{kind['en']} {size}".strip(), "fr": f"{kind['fr']} {size}".strip()}
        suppliers = [s["name"] for s in train["suppliers"] if system["ref"] in s["systems"]]
        parts[ref] = {"en": names["en"], "fr": names["fr"], "unit": kind["unit"],
                      "supplier": supplier or rng.choice(suppliers),
                      "cost": round(rng.uniform(*kind["price"]), 2)}

    def add_design(ref, system, position, components, hand, supplier=None):
        for component in components:
            add_part(component, system, supplier)
        designs[ref] = {"system": system["ref"], "position": position["en"], "en": position["en"],
                        "fr": position["fr"], "components": components, "hand": hand}

    def random_quantity(ref):
        kind = train["kinds"][ref[:2]]
        low, high = kind["qty"]
        return rng.randint(low, high) if kind["unit"] == "pcs" else round(rng.uniform(low, high), 1)

    def random_design(system, size):
        """size components, mostly new parts, sometimes one already used in this system."""
        components = {}
        shared = [r for r, d in designs.items() if d["system"] == system["ref"] and not d["hand"]
                  for r in d["components"]]
        while len(components) < size:
            if shared and rng.random() < 0.15:
                ref = rng.choice(shared)
            else:
                ref = new_ref(rng.choice(system["kinds"]), taken, rng)
            if ref not in components:
                components[ref] = random_quantity(ref)
        return components

    for system in train["systems"]:
        for position in system["positions"]:
            key = lambda v: (v, system["ref"], position["en"])
            written = findings["positions"].get(position["en"])

            if written:  # hand-written in findings.json
                for ref, spec in written["designs"].items():
                    if "copy_of" in spec:
                        components = _apply_changes(designs[spec["copy_of"]]["components"], spec.get("changes", []))
                    else:
                        components = dict(map(tuple, spec["components"]))
                    add_design(ref, system, position, components, hand=True, supplier=spec.get("supplier"))
                for v in variants:
                    use[key(v)] = written["use"][v]

            elif position["type"] == "common":  # one design in all variants
                ref = new_ref(position["prefix"], taken, rng)
                add_design(ref, system, position, random_design(system, rng.randint(3, 5)), hand=False)
                for v in variants:
                    use[key(v)] = ref

            else:  # split by option: one design per value group, 4 lines or more apart
                base = random_design(system, rng.randint(5, 6))
                for group in _groups(train["variants"], position["split_by"]):
                    ref = new_ref(position["prefix"], taken, rng)
                    add_design(ref, system, position, dict(base), hand=False)
                    for v in group:
                        use[key(v)] = ref
                    # the next group swaps 4 or 5 components of the base for new ones
                    base = dict(base)
                    for old in rng.sample(sorted(base), rng.randint(4, 5)):
                        del base[old]
                        new = new_ref(old[:2], taken, rng)
                        base[new] = random_quantity(new)

    return {"parts": parts, "designs": designs, "use": use}


def _hand_refs(findings):
    refs = set(findings["parts"])
    for position in findings["positions"].values():
        for ref, spec in position["designs"].items():
            refs.add(ref)
            refs.update(c[0] for c in spec.get("components", []))
            for change in spec.get("changes", []):
                refs.update(v for v in [change.get("for"), (change.get("add") or [None])[0]] if v)
    return refs


def _apply_changes(components, changes):
    """A copy of a design with lines swapped, added, or given another quantity."""
    result = dict(components)
    for change in changes:
        if "swap" in change:
            result = {(change["for"] if ref == change["swap"] else ref): q for ref, q in result.items()}
        elif "add" in change:
            result[change["add"][0]] = change["add"][1]
        elif "quantity" in change:
            result[change["quantity"][0]] = change["quantity"][1]
    return result


def _groups(variants, attribute):
    """Variants grouped by an option. Cars are grouped as short (6, 7) and long (8, 10)."""
    groups = {}
    for v in variants:
        value = v[attribute] if attribute != "cars" else v["cars"] >= 8
        groups.setdefault(value, []).append(v["variant_id"])
    return list(groups.values())


# --- the clean rows ----------------------------------------------------------

def build_bom(train, model):
    """Clean BOM rows: one per parent-child link per variant, columns of plm_bom_export.csv.

    Each row also carries, under keys starting with '_', what it truly is. Those
    keys are never written to the client files.
    """
    rows = []

    def add(variant, level, parent, child, description, quantity, unit):
        row = {"variant_id": variant["variant_id"], "cars": str(variant["cars"]),
               "speed_class_kmh": str(variant["speed_class_kmh"]), "interior": variant["interior"],
               "level": str(level), "parent_ref": parent, "child_ref": child,
               "description": description, "quantity": number(quantity), "unit": unit}
        rows.append({**row, "_id": str(len(rows) + 1), "_clean": dict(row)})

    for variant in train["variants"]:
        v = variant["variant_id"]
        for system in train["systems"]:
            add(variant, 2, v, system["ref"], system["en"], 1, "pcs")
        for system in train["systems"]:
            for position in system["positions"]:
                ref = model["use"][(v, system["ref"], position["en"])]
                count = position["per_car"] * variant["cars"] if "per_car" in position else position["per_train"]
                add(variant, 3, system["ref"], ref, position["en"], count, "pcs")
        for system in train["systems"]:
            for position in system["positions"]:
                ref = model["use"][(v, system["ref"], position["en"])]
                for component, quantity in model["designs"][ref]["components"].items():
                    part = model["parts"][component]
                    add(variant, 4, ref, component, part["en"], quantity, part["unit"])
    return rows


def build_erp(model, bom):
    """Clean ERP rows: one per component found in the BOM, columns of erp_items.csv."""
    from .refs import erp_form
    rows = []
    for ref in sorted({row["child_ref"] for row in bom if row["level"] == "4"}):
        part = model["parts"][ref]
        row = {"item_ref": erp_form(ref), "description": part["fr"].upper(), "supplier": part["supplier"],
               "unit_cost_eur": f"{part['cost']:.2f}".replace(".", ","), "price_unit": part["unit"]}
        rows.append({**row, "_id": str(len(rows) + 1), "_clean": dict(row), "_part": ref})
    return rows


# --- the notes ---------------------------------------------------------------

def build_note_facts(findings, model, settings, rng):
    """One fact list per note. The text is written from these facts, never the reverse.

    Keys: note_id, date, relation, ref_a, ref_b (the real references), written_a,
    written_b (as they appear in the note), part_a, part_b (what the parts are),
    in_field (is written_a in the 'reference' field, or only in the text),
    language, topic, option, overridden_by.
    """
    noise = settings["noise"]
    true_refs = sorted(set(model["parts"]) | set(model["designs"]))
    in_a_relation = {ref for f in findings["findings"] for note in f.get("notes", []) for ref in note["refs"]}
    plain_refs = [ref for ref in true_refs if ref not in in_a_relation]
    first, last = datetime.date(2019, 1, 1).toordinal(), datetime.date(2026, 6, 30).toordinal()
    random_date = lambda: datetime.date.fromordinal(rng.randint(first, last)).isoformat()

    names = {**model["parts"], **model["designs"]}
    name = lambda ref: names[ref]["en"] if ref else ""

    def fact(relation, refs, date=None, topic="", option="", finding=""):
        a, b = (list(refs) + ["", ""])[:2]
        return {"date": date or random_date(), "relation": relation, "ref_a": a, "ref_b": b,
                "written_a": a, "written_b": b, "part_a": name(a), "part_b": name(b), "topic": topic, "option": option,
                "overridden_by": "", "_finding": finding, "_overridden": False}

    # 1. the notes required by the findings
    facts = []
    for finding in findings["findings"]:
        for note in finding.get("notes", []):
            f = fact(note["relation"], note["refs"], note.get("date"), option=note.get("option", ""), finding=finding["id"])
            f["_overridden"] = note.get("overridden", False)
            facts.append(f)

    # 2. a few relations are stated a second time in a later note, as happens in practice
    restatable = [f for f in facts if f["relation"] in ("obsolete", "superseded_by", "interchangeable_with")]
    for f in rng.sample(restatable, settings["notes_restated"]):
        later = datetime.date.fromisoformat(f["date"]).toordinal() + rng.randint(60, 400)
        facts.append(fact(f["relation"], [f["ref_a"], f["ref_b"]], datetime.date.fromordinal(min(later, last)).isoformat(),
                          topic="restates an earlier note", option=f["option"], finding=f["_finding"]))
    relation_facts = list(facts)

    # 3. noise on the relation notes: a mistyped reference, and the reference only in the text
    # (not on look-alike references: those notes are what tells the two parts apart)
    taken = set(true_refs)
    lookalikes = {ref for f in findings["findings"] if f["kind"] == "lookalike_references" for ref in (f["a"], f["b"])}
    typable = [f for f in relation_facts if not {f["ref_a"], f["ref_b"]} & lookalikes]
    for f in rng.sample(typable, round(noise["note_mistyped_reference"] * len(relation_facts))):
        side = "b" if f["ref_b"] else "a"   # the reference being pointed to
        f[f"written_{side}"] = typo(f[f"ref_{side}"], true_refs, taken, rng)
    only_in_text = set(map(id, rng.sample(relation_facts, round(noise["note_reference_only_in_text"] * len(relation_facts)))))
    for f in relation_facts:
        f["in_field"] = id(f) not in only_in_text

    # 4. the plain notes: no relation, but most still mention a part
    topics = TRAP_TOPICS + [rng.choice(PLAIN_TOPICS) for _ in range(settings["notes_total"] - len(facts) - len(TRAP_TOPICS))]
    for topic in topics:
        ref = "" if rng.random() < 0.1 else rng.choice(plain_refs)
        f = fact("", [ref], topic=topic)
        f["in_field"] = bool(ref) and rng.random() < 0.5
        facts.append(f)

    # 5. language, then identifiers in date order
    count = len(facts)
    languages = ["fr"] * round(count / 2) + ["en"] * round(count / 3)
    languages += ["mixed"] * (count - len(languages))
    rng.shuffle(languages)
    facts.sort(key=lambda f: f["date"])
    number_ = 100
    for f, language in zip(facts, languages):
        number_ += rng.randint(1, 9)
        f["note_id"], f["language"] = f"TN-{number_:04d}", language

    # 6. where two notes of one finding contradict each other, record which one wins
    for f in facts:
        if f["_overridden"]:
            f["overridden_by"] = next(g["note_id"] for g in facts
                                      if g["_finding"] == f["_finding"] and g["relation"] and not g["_overridden"]
                                      and {g["ref_a"], g["ref_b"]} == {f["ref_a"], f["ref_b"]})
    return [{k: v for k, v in f.items() if not k.startswith("_")} for f in facts]


def note_rows(facts, texts):
    """The rows of technical_notes.jsonl: the facts joined with their written text."""
    return [{"note_id": f["note_id"], "date": f["date"],
             "reference": f["written_a"] if f["in_field"] else "", "text": texts[f["note_id"]]}
            for f in facts]
