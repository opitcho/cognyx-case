"""Part 3 of the plan: one function per kind of noise.

Each function changes some rows in place and returns the list of changes it made.
None of them knows about findings: protected() tells them what to leave alone
and what they must touch.
"""
from .refs import erp_form, typo

BOM, ERP = "plm_bom_export.csv", "erp_items.csv"
PIECE_SYNONYMS_BOM = ["ea", "U", "PCE"]
PIECE_SYNONYMS_ERP = ["PCE", "U", "EA"]
SMALLER_UNIT = {"m": "mm", "kg": "g"}


def protected(findings, bom):
    """The rules of part 3, computed once from findings.json and the clean BOM."""
    entries = findings["findings"]
    content = {}  # sub-assembly -> {component: quantity}
    for row in bom:
        if row["level"] == "4":
            content.setdefault(row["parent_ref"], {})[row["child_ref"]] = row["quantity"]

    differing = set()  # components on the differing lines of near pairs: their price is needed
    for f in entries:
        if f["kind"].startswith("near_pair"):
            a, b = content[f["a"]], content[f["b"]]
            differing |= {c for c in set(a) | set(b) if a.get(c) != b.get(c)}
    no_price = {f["noise"]["no_price"] for f in entries if "no_price" in f.get("noise", {})}
    in_v1 = {row["child_ref"] for row in bom if row["level"] == "4" and row["variant_id"] == "V1"}

    return {
        "true_refs": sorted({row["child_ref"] for row in bom if row["level"] in "34"}),
        # either member of a look-alike pair never gets a mistyped twin
        "no_twin": {ref for f in entries if f["kind"] == "lookalike_references" for ref in (f["a"], f["b"])},
        # a repeated line with another quantity never lands in a hand-written sub-assembly
        "planted_subassemblies": {ref for position in findings["positions"].values() for ref in position["designs"]},
        # components of V1, and differing lines of near pairs, keep their price
        "keep_price": (in_v1 | differing) - no_price,
        # noise that findings.json asks for
        "force_twin": [f["noise"]["twin"] for f in entries if "twin" in f.get("noise", {})],
        "force_unit": [f["noise"]["unit"] for f in entries if "unit" in f.get("noise", {})],
        "force_no_price": no_price,
    }


# --- helpers -----------------------------------------------------------------

def _set(row, file, field, value, kind, changes):
    """Change one value and log it."""
    if row[field] != value:
        changes.append({"file": file, "row_id": row["_id"], "field": field,
                        "clean_value": row["_clean"][field], "written_value": value, "kind": kind})
        row[field] = value


def _copy_row(rows, source, file, kind, changes):
    """Insert a copy of a row right after it and log it. Its id is '<source id>+<n>'."""
    base = source["_id"].split("+")[0]
    n = 1 + sum(1 for r in rows if r["_id"].startswith(base + "+"))
    copy = {**source, "_id": f"{base}+{n}", "_clean": dict(source["_clean"])}
    rows.insert(next(i for i, r in enumerate(rows) if r["_id"] == base) + 1, copy)
    changes.append({"file": file, "row_id": copy["_id"], "field": "", "clean_value": "", "written_value": "", "kind": kind})
    return copy


def _pick(items, weights, count, rng):
    """count distinct items, the heavier ones more likely."""
    items, weights, picked = list(items), list(weights), []
    while items and len(picked) < count:
        i = rng.choices(range(len(items)), weights)[0]
        picked.append(items.pop(i))
        weights.pop(i)
    return picked


def _v1_first(rows, weight, rng):
    """One variant among those of the rows, V1 being `weight` times more likely."""
    variants = sorted({r["variant_id"] for r in rows})
    return rng.choices(variants, [weight if v == "V1" else 1 for v in variants])[0]


def _number(text):
    return float(text.replace(",", "."))


def _plain(value):
    return str(int(value)) if float(value).is_integer() else f"{value:.5f}".rstrip("0")


# --- 1. mistyped twin of a reference -----------------------------------------

def reference_twins(bom, erp, rate, skip, v1_weight, rng):
    """Some occurrences of a part are written under a mistyped reference.

    A component twin also gets its own ERP row. A sub-assembly twin is used both
    on its own row and as the parent of its components, in one variant.
    """
    changes, taken = [], set(skip["true_refs"]) | {r["item_ref"] for r in erp}

    def twin_component(ref, rows):
        written = typo(ref, skip["true_refs"], taken, rng)
        for row in rows:
            _set(row, BOM, "child_ref", written, "reference_twin", changes)
        if all(r["item_ref"] != erp_form(written) for r in erp):
            source = next(r for r in erp if r["_part"] == ref)
            _set(_copy_row(erp, source, ERP, "reference_twin", changes), ERP, "item_ref", erp_form(written), "reference_twin", changes)

    def twin_subassembly(ref, variant):
        written = typo(ref, skip["true_refs"], taken, rng)
        for row in bom:
            if row["variant_id"] == variant and row["_clean"]["child_ref"] == ref:
                _set(row, BOM, "child_ref", written, "reference_twin", changes)
            if row["variant_id"] == variant and row["_clean"]["parent_ref"] == ref:
                _set(row, BOM, "parent_ref", written, "reference_twin", changes)

    occurrences = {}  # true reference -> its rows as a child
    for row in bom:
        if row["level"] in "34":
            occurrences.setdefault(row["child_ref"], []).append(row)

    for subassembly, component in skip["force_twin"]:
        twin_component(component, [r for r in occurrences[component] if r["parent_ref"] == subassembly])
    forced = {component for _, component in skip["force_twin"]}

    # a twin needs at least one other occurrence that keeps the right spelling
    candidates = [ref for ref, rows in occurrences.items()
                  if len(rows) >= 2 and ref not in skip["no_twin"] and ref not in forced]
    weights = [v1_weight if any(r["variant_id"] == "V1" for r in occurrences[ref]) else 1 for ref in candidates]
    for ref in _pick(candidates, weights, round(rate * len(occurrences)) - len(forced), rng):
        rows = occurrences[ref]
        variant = _v1_first(rows, v1_weight, rng)
        if rows[0]["level"] == "3":
            twin_subassembly(ref, variant)
        else:
            in_variant = [r for r in rows if r["variant_id"] == variant]
            twin_component(ref, in_variant if len(in_variant) < len(rows) else in_variant[:1])
    return changes


# --- 2. repeated BOM line ----------------------------------------------------

def repeated_lines(bom, rate, other_quantity_share, skip, v1_weight, rng):
    """A component line is written twice, a third of the time with another quantity."""
    changes = []
    lines = [r for r in bom if r["level"] == "4"]
    count = round(rate * len(bom))
    with_other_quantity = round(other_quantity_share * count)
    weight = lambda r: v1_weight if r["variant_id"] == "V1" else 1

    safe = [r for r in lines if r["_clean"]["parent_ref"] not in skip["planted_subassemblies"]]
    for row in _pick(safe, map(weight, safe), with_other_quantity, rng):
        copy = _copy_row(bom, row, BOM, "repeated_line", changes)
        quantity = _number(row["quantity"])
        _set(copy, BOM, "quantity", _plain(round(quantity * rng.choice([0.5, 1.5, 2]), 1) or 1), "repeated_line", changes)
    rest = [r for r in lines if not any(c["row_id"].startswith(r["_id"] + "+") for c in changes)]
    for row in _pick(rest, map(weight, rest), count - with_other_quantity, rng):
        _copy_row(bom, row, BOM, "repeated_line", changes)
    return changes


# --- 3. mixed units ----------------------------------------------------------

def mixed_units(bom, erp, rate, skip, v1_weight, rng):
    """The same quantity in another unit: 2.4 m as 2400 mm, pcs as ea / U / PCE.

    Quantity and unit (or price and price unit) always change together, so the
    clean value can be recovered.
    """
    changes = []

    def convert_bom(row):
        if row["unit"] in SMALLER_UNIT:
            _set(row, BOM, "quantity", _plain(_number(row["quantity"]) * 1000), "mixed_unit", changes)
            _set(row, BOM, "unit", SMALLER_UNIT[row["unit"]], "mixed_unit", changes)
        elif row["unit"] == "pcs":
            _set(row, BOM, "unit", rng.choice(PIECE_SYNONYMS_BOM), "mixed_unit", changes)

    def convert_erp(row):
        if row["price_unit"] in SMALLER_UNIT:
            cost = f"{_number(row['unit_cost_eur']) / 1000:.5f}".replace(".", ",")
            _set(row, ERP, "unit_cost_eur", cost, "mixed_unit", changes)
            _set(row, ERP, "price_unit", SMALLER_UNIT[row["price_unit"]], "mixed_unit", changes)
        elif row["price_unit"] == "pcs":
            _set(row, ERP, "price_unit", rng.choice(PIECE_SYNONYMS_ERP), "mixed_unit", changes)

    lines = {}  # true component -> its BOM rows
    for row in bom:
        if row["level"] == "4":
            lines.setdefault(row["_clean"]["child_ref"], []).append(row)

    for subassembly, component in skip["force_unit"]:
        for row in lines[component]:
            if row["_clean"]["parent_ref"] == subassembly:
                convert_bom(row)
    forced = {component for _, component in skip["force_unit"]}

    items = [ref for ref in sorted(lines) if ref not in forced]
    for ref in rng.sample(items, round(rate * len(lines)) - len(forced)):
        where = rng.choices(["bom", "erp", "both"], [60, 25, 15])[0]
        if where in ("bom", "both"):
            variant = _v1_first(lines[ref], v1_weight, rng)
            for row in lines[ref]:
                if row["variant_id"] == variant:
                    convert_bom(row)
        if where in ("erp", "both"):
            convert_erp(next(r for r in erp if r["_part"] == ref))
    return changes


# --- 4. language -------------------------------------------------------------

def language_switch(bom, erp, names, rate, v1_weight, rng):
    """Some BOM descriptions are in French, some ERP descriptions in English."""
    changes = []
    rows = [r for r in bom if r["level"] in "34"]
    weights = [v1_weight if r["variant_id"] == "V1" else 1 for r in rows]
    for row in _pick(rows, weights, round(rate * len(bom)), rng):
        _set(row, BOM, "description", names[row["_clean"]["child_ref"]]["fr"], "language", changes)
    for row in rng.sample(erp, round(rate * len(erp))):
        _set(row, ERP, "description", names[row["_part"]]["en"].upper(), "language", changes)
    return changes


# --- 5. cost conflict --------------------------------------------------------

def cost_conflicts(erp, rate, rng):
    """A twin row carries another price than the row it was copied from."""
    changes = []
    twins = [r for r in erp if "+" in r["_id"]]
    items = sum(1 for r in erp if "+" not in r["_id"])
    for row in rng.sample(twins, min(round(rate * items), len(twins))):
        cost = _number(row["unit_cost_eur"]) * (1 + rng.choice([-1, 1]) * rng.uniform(0.04, 0.15))
        decimals = len(row["unit_cost_eur"].split(",")[1])
        _set(row, ERP, "unit_cost_eur", f"{cost:.{decimals}f}".replace(".", ","), "cost_conflict", changes)
    return changes


# --- 6. supplier name variants ----------------------------------------------

def supplier_variants(erp, suppliers, rng):
    """A supplier with several spellings is written under any of them."""
    changes = []
    spellings = {s["name"]: s["spellings"] for s in suppliers if "spellings" in s}
    for row in erp:
        if row["supplier"] in spellings:
            _set(row, ERP, "supplier", rng.choice(spellings[row["supplier"]]), "supplier_variant", changes)
    return changes


# --- 7. missing values -------------------------------------------------------

def missing_values(erp, rate, skip, suppliers, rng):
    """A supplier or a price is empty, or the supplier is a filler word."""
    changes = []
    noisy = {s["name"] for s in suppliers if "spellings" in s}  # two suppliers carry most of it
    for row in erp:
        if row["_part"] in skip["force_no_price"]:
            _set(row, ERP, "unit_cost_eur", "", "missing_value", changes)

    cells = [(r, "supplier") for r in erp] + [(r, "unit_cost_eur") for r in erp if r["_part"] not in skip["keep_price"]]
    cells = [(r, field) for r, field in cells if r[field] != ""]
    weights = [4 if r["_clean"]["supplier"] in noisy else 1 for r, _ in cells]
    for row, field in _pick(cells, weights, round(rate * 2 * len(erp)) - len(changes), rng):
        filler = rng.choice(["", "", "UNKNOWN", "N/A"]) if field == "supplier" else ""
        _set(row, ERP, field, filler, "missing_value", changes)
    return changes
