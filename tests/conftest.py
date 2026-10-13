"""Shared fixtures: the generated raw files, and a small hand-made set for cases the generated data lacks."""

from pathlib import Path

import pytest

from pipeline.ingest import Raw, read_raw
from pipeline.rules import run_rules

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def raw() -> Raw:
    return read_raw(ROOT / "data" / "raw")


@pytest.fixture(scope="session")
def rules_log(tmp_path_factory) -> Path:
    """A claim log holding only the rules' claims on the generated files. Tests copy it before appending."""
    log = tmp_path_factory.mktemp("log") / "claims.jsonl"
    run_rules(log, ROOT / "data" / "raw")
    return log


def bom_row(row_no, variant, level, parent, child, description="Part", quantity="1", unit="pcs"):
    return {"row_no": row_no, "variant_id": variant, "cars": "6", "speed_class_kmh": "160", "interior": "suburban",
            "level": str(level), "parent_ref": parent, "child_ref": child, "description": description,
            "quantity": quantity, "unit": unit}


@pytest.fixture
def tiny() -> Raw:
    """Two variants, one system, two door leaves written differently, one note."""
    bom = [
        bom_row(1, "V1", 2, "V1", "DOOR-SYS-01", "Door system"),
        bom_row(2, "V1", 3, "DOOR-SYS-01", "DR-1042", "Door leaf", "2"),
        bom_row(3, "V1", 4, "DR-1042", "JT-218", "Door seal", "2.4", "m"),
        bom_row(4, "V1", 4, "DR-1042", "AC-501", "Actuator"),
        bom_row(5, "V2", 2, "V2", "DOOR-SYS-01", "Door system"),
        bom_row(6, "V2", 3, "DOOR-SYS-01", "PT-7731", "Door leaf", "2"),
        bom_row(7, "V2", 4, "PT-7731", "JT 218", "Joint de porte", "2400", "mm"),
        bom_row(8, "V2", 4, "PT-7731", "AC-501", "Actuator"),
    ]
    erp = [
        {"row_no": 1, "item_ref": "JT218", "description": "JOINT DE PORTE", "supplier": "Faiveley",
         "unit_cost_eur": "38,50", "price_unit": "m"},
        {"row_no": 2, "item_ref": "AC501", "description": "ACTIONNEUR", "supplier": "FAIVELEY TRANSPORT SAS",
         "unit_cost_eur": "412,00", "price_unit": "pcs"},
    ]
    notes = [{"row_no": 1, "note_id": "TN-0001", "date": "2025-01-10", "reference": "PT-7731",
              "text": "PT-7731 = ex DR-1042, renumbered. Actuator AC-501 superseded by AC-560."}]
    return Raw(bom, erp, notes)
