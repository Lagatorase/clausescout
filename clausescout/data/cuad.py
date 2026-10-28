"""Loading CUAD v1 into simple Python objects."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

RAW_DIR = Path("data/raw")
MASTER_JSON = RAW_DIR / "CUAD_v1" / "CUAD_v1.json"
TRAIN_JSON = RAW_DIR / "cuad_json" / "train_separate_questions.json"
TEST_JSON = RAW_DIR / "cuad_json" / "test.json"
PDF_DIR = RAW_DIR / "CUAD_v1" / "full_contract_pdf"
SPLIT_DIR = Path(__file__).resolve().parents[2] / "experiments" / "splits"

# The 41 CUAD categories in the order the dataset lists them.
CATEGORIES: list[str] = [
    "Document Name", "Parties", "Agreement Date", "Effective Date", "Expiration Date",
    "Renewal Term", "Notice Period To Terminate Renewal", "Governing Law", "Most Favored Nation",
    "Non-Compete", "Exclusivity", "No-Solicit Of Customers", "Competitive Restriction Exception",
    "No-Solicit Of Employees", "Non-Disparagement", "Termination For Convenience",
    "Rofr/Rofo/Rofn", "Change Of Control", "Anti-Assignment", "Revenue/Profit Sharing",
    "Price Restrictions", "Minimum Commitment", "Volume Restriction", "Ip Ownership Assignment",
    "Joint Ip Ownership", "License Grant", "Non-Transferable License",
    "Affiliate License-Licensor", "Affiliate License-Licensee",
    "Unlimited/All-You-Can-Eat-License", "Irrevocable Or Perpetual License",
    "Source Code Escrow", "Post-Termination Services", "Audit Rights", "Uncapped Liability",
    "Cap On Liability", "Liquidated Damages", "Warranty Duration", "Insurance",
    "Covenant Not To Sue", "Third Party Beneficiary",
]

# The types that matter most in a due diligence report, so I weight the analysis towards them.
HIGH_STAKES: list[str] = [
    "Cap On Liability", "Uncapped Liability", "Termination For Convenience", "Change Of Control",
    "Anti-Assignment", "Exclusivity", "Non-Compete", "Governing Law",
]


@dataclass
class Span:
    text: str
    start: int

    @property
    def end(self) -> int:
        return self.start + len(self.text)


@dataclass
class Contract:
    id: str
    text: str
    # Category name to the list of gold spans (empty list means the clause is absent).
    labels: dict[str, list[Span]] = field(default_factory=dict)

    def present(self) -> set[str]:
        return {c for c, spans in self.labels.items() if spans}


def _category_from_qa_id(qa_id: str) -> str:
    # Question ids look like "<title>__<Category>" in the master file.
    return qa_id.split("__", 1)[1]


@lru_cache(maxsize=1)
def load_all(path: Path = MASTER_JSON) -> dict[str, Contract]:
    """Every contract keyed by its CUAD title, with all answers per category."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))["data"]
    contracts: dict[str, Contract] = {}
    for item in raw:
        para = item["paragraphs"][0]
        c = Contract(id=item["title"], text=para["context"])
        for qa in para["qas"]:
            cat = _category_from_qa_id(qa["id"])
            c.labels[cat] = [Span(a["text"], a["answer_start"]) for a in qa["answers"]]
        # I make sure every category is present as a key, even if empty.
        for cat in CATEGORIES:
            c.labels.setdefault(cat, [])
        contracts[c.id] = c
    return contracts


def official_split() -> tuple[list[str], list[str]]:
    """Contract titles in CUAD's official train and test files."""
    def titles(p: Path) -> list[str]:
        return [d["title"] for d in json.loads(p.read_text(encoding="utf-8"))["data"]]
    return titles(TRAIN_JSON), titles(TEST_JSON)


def load_split(name: str) -> list[Contract]:
    """Contracts for 'train', 'val' or 'test' using the committed ID lists."""
    ids = (SPLIT_DIR / f"{name}.txt").read_text(encoding="utf-8").splitlines()
    contracts = load_all()
    return [contracts[i] for i in ids if i]


def _pdf_key(name: str) -> str:
    # PDF filenames differ from CUAD titles in small ways: trailing spaces, decomposed accents
    # (e followed by a combining accent) and a trailing "-". I compare a cleaned-up form.
    return unicodedata.normalize("NFC", name).strip().rstrip("-_ ").lower()


def pdf_path(contract_id: str) -> Path | None:
    """Finds the original PDF for a contract, if there is one."""
    index = _pdf_index()
    key = _pdf_key(contract_id)
    if key in index:
        return index[key]
    # One PDF name has an extra suffix ("..._Option Agreement"), so I fall back to a unique
    # prefix match, and give up rather than guess if there are several.
    matches = [p for k, p in index.items() if k.startswith(key)]
    return matches[0] if len(matches) == 1 else None


@lru_cache(maxsize=1)
def _pdf_index() -> dict[str, Path]:
    # The PDFs sit in nested folders with mixed-case extensions, so I index them once by stem.
    return {_pdf_key(p.stem): p for p in PDF_DIR.rglob("*") if p.suffix.lower() == ".pdf"}
