from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Callable

import yaml

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


@dataclass
class RuleDef:
    rule_id: str
    category: str
    subcategory: str
    title: str
    description: str
    severity_default: str
    detection_type: str
    detector_ref: str
    trigger_ref: str = ""
    judgment_ref: str = ""
    applies_to: str = ""
    remediation_template: str = ""
    verification_template: str = ""
    confidence_default: str = "High"


class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, RuleDef] = {}
        self._detector_cache: dict[str, Callable] = {}

    def load(self) -> "RuleRegistry":
        self._rules.clear()
        for yaml_path in sorted(DEFINITIONS_DIR.glob("*.yaml")):
            entries = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or []
            for entry in entries:
                rule = RuleDef(**entry)
                self._rules[rule.rule_id] = rule
        return self

    def all(self) -> list[RuleDef]:
        return list(self._rules.values())

    def get(self, rule_id: str) -> RuleDef:
        return self._rules[rule_id]

    def severity_for(self, rule_id: str) -> str:
        return self._rules[rule_id].severity_default

    def confidence_for(self, rule_id: str) -> str:
        return self._rules[rule_id].confidence_default

    def resolve_detector(self, detector_ref: str) -> Callable:
        """Resolve a dotted "module.function" ref against app.rules.detectors.*.
        Fails fast (ImportError/AttributeError) on drift between the YAML
        rulebook and the actual code -- there is deliberately no silent fallback.
        """
        if detector_ref in self._detector_cache:
            return self._detector_cache[detector_ref]
        module_name, func_name = detector_ref.rsplit(".", 1)
        module = import_module(f"app.rules.detectors.{module_name}")
        func = getattr(module, func_name)
        self._detector_cache[detector_ref] = func
        return func

    def detectors_for(self, applies_to: str) -> list[Callable]:
        """Distinct detector callables among rules matching applies_to, in
        stable order. Distinct because several rule_ids (e.g. JQA-SEC-*) share
        one detector function that assigns the specific rule_id per finding.
        """
        seen: dict[str, Callable] = {}
        for rule in self._rules.values():
            if rule.applies_to == applies_to and rule.detector_ref:
                seen.setdefault(rule.detector_ref, self.resolve_detector(rule.detector_ref))
        return list(seen.values())


registry = RuleRegistry().load()
