"""Applying a YAML playbook of risk rules to the clauses found in one contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from clausescout.findings import Finding

DEFAULT_PLAYBOOK = Path(__file__).parent / "default.yaml"
SEVERITIES = ("high", "medium", "low")
# Rules whose conditions only look at CUAD clause types can be scored against CUAD's labels.
LABEL_CONDITIONS = {"present", "absent", "quote_matches", "quote_lacks"}


@dataclass
class Rule:
    id: str
    severity: str
    title: str
    explanation: str
    condition: dict

    @property
    def measurable(self) -> bool:
        return _condition_kinds(self.condition) <= LABEL_CONDITIONS


@dataclass
class Flag:
    rule: Rule
    # The findings that raised the flag, so the report can quote them. Empty for absences.
    evidence: list[Finding] = field(default_factory=list)


def _condition_kinds(cond: dict) -> set[str]:
    if "all" in cond:
        return set().union(*(_condition_kinds(c) for c in cond["all"]))
    return set(cond)


def load_playbook(path: str | Path = DEFAULT_PLAYBOOK) -> list[Rule]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    rules = [Rule(**r) for r in data["rules"]]
    for r in rules:
        if r.severity not in SEVERITIES:
            raise ValueError(f"Rule {r.id} has unknown severity {r.severity!r}")
    return rules


def _check(cond: dict, by_type: dict[str, list[Finding]], text: str) -> tuple[bool, list]:
    """Whether one condition holds, and the findings that show it."""
    if "all" in cond:
        evidence = []
        for c in cond["all"]:
            ok, ev = _check(c, by_type, text)
            if not ok:
                return False, []
            evidence += ev
        return True, evidence
    (kind, arg), = cond.items()
    if kind == "present":
        return bool(by_type.get(arg)), by_type.get(arg, [])
    if kind == "absent":
        return not by_type.get(arg), []
    if kind in ("quote_matches", "quote_lacks"):
        found = by_type.get(arg["type"], [])
        pattern = re.compile(arg["pattern"], re.IGNORECASE)
        hits = [f for f in found if pattern.search(f.text)]
        if kind == "quote_matches":
            return bool(hits), hits
        # "Lacks" only fires when the clause exists and none of its quotes has the pattern.
        return bool(found) and not hits, found
    if kind == "text_matches":
        return bool(re.search(arg, text, re.IGNORECASE)), []
    if kind == "text_lacks":
        return not re.search(arg, text, re.IGNORECASE), []
    raise ValueError(f"Unknown condition {kind!r}")


def apply_playbook(rules: list[Rule], findings: list[Finding], text: str) -> list[Flag]:
    """Flags for one contract, most severe first. findings should already be thresholded."""
    by_type: dict[str, list[Finding]] = {}
    for f in findings:
        by_type.setdefault(f.category, []).append(f)
    flags = []
    for rule in rules:
        ok, evidence = _check(rule.condition, by_type, text)
        if ok:
            flags.append(Flag(rule, evidence))
    flags.sort(key=lambda fl: SEVERITIES.index(fl.rule.severity))
    return flags
