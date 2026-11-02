"""The Singapore test set: which clause types I label, and reading the labels back.

Labelling all 41 CUAD types on 15 contracts would take far too long, so I label 11:
- the 8 high-stakes types from selection rule 2, scored the same way as on CUAD, and
- 3 types for the playbook rules CUAD has no label for (arbitration, SIAC, data protection),
  so those rules can finally be measured.

For each type a contract is marked present (with the exact quote or quotes) or absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from clausescout.data.cuad import HIGH_STAKES

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "datasets" / "singapore" / "manifest.yaml"
LABEL_DIR = ROOT / "datasets" / "singapore" / "labels"
TEXT_DIR = ROOT / "data" / "singapore" / "text"

PLAYBOOK_TYPES = ["Arbitration", "SIAC Arbitration", "Data Protection"]
LABEL_TYPES = HIGH_STAKES + PLAYBOOK_TYPES

# What counts as present, shown next to each type in the labelling tool. The first 8 are short
# versions of CUAD's own descriptions, so the labels mean the same as CUAD's.
GUIDANCE = {
    "Cap On Liability": "A cap on the amount of damages or liability for a breach, or a time "
                        "limit for bringing claims.",
    "Uncapped Liability": "Liability that is expressly not capped, for example for breach of "
                          "confidentiality, IP infringement or indemnities.",
    "Termination For Convenience": "A party can terminate without cause, usually with notice.",
    "Change Of Control": "A right (to terminate, consent or be notified) triggered by a change "
                         "of control, merger or sale of a party.",
    "Anti-Assignment": "Assignment needs the other party's consent or notice.",
    "Exclusivity": "An exclusive dealing commitment: buying all requirements from one party, "
                   "or not selling, licensing or working with third parties, during or after "
                   "the contract.",
    "Non-Compete": "A restriction on a party competing with the other, or operating in a "
                   "place or business sector.",
    "Governing Law": "Which country's or state's law governs the contract.",
    "Arbitration": "Disputes are resolved by arbitration (any rules or institution).",
    "SIAC Arbitration": "Arbitration under the Singapore International Arbitration Centre "
                        "(SIAC) or its rules.",
    "Data Protection": "A clause about personal data, data protection, privacy or the PDPA.",
}

# The playbook rules these labels measure, and when each rule's flag is right.
RULE_TRUTH = {
    "no-arbitration": lambda lab: lab["Arbitration"] == "absent",
    "arbitration-not-siac": lambda lab: (lab["Arbitration"] == "present"
                                         and lab["SIAC Arbitration"] == "absent"),
    "no-data-protection": lambda lab: lab["Data Protection"] == "absent",
}


def contract_ids(manifest: Path = MANIFEST) -> list[str]:
    return [c["id"] for c in yaml.safe_load(manifest.read_text(encoding="utf-8"))["contracts"]]


def load_labels(cid: str, label_dir: Path = LABEL_DIR) -> dict:
    path = Path(label_dir) / f"{cid}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"contract": cid, "labels": {}}


def is_complete(labels: dict) -> bool:
    """A contract is only scored once every one of the 11 types has a decision."""
    return all(t in labels.get("labels", {}) for t in LABEL_TYPES)
