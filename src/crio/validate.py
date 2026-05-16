from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from crio.schema.model import CRIOSchema


class ValidationReport:
    def __init__(self, valid: bool, errors: list[dict], schema: CRIOSchema | None):
        self.valid = valid
        self.errors = errors
        self.schema = schema

    def __repr__(self):
        if self.valid:
            return "ValidationReport(valid=True)"
        return f"ValidationReport(valid=False, errors={len(self.errors)})"

    def print_report(self):
        if self.valid:
            print("✓ Schema valid")
            print(f"  Phenotype:         {self.schema.phenotype.name}")
            print(f"  Version:           {self.schema.phenotype.version}")
            print(f"  Validation status: {self.schema.phenotype.validation_status.value}")
            print(f"  Deposit eligible:  {self.schema.contribution.deposit_eligible}")
            print(f"  SCE tier:          {self.schema.compute.sce_tier.value}")
        else:
            print(f"✗ Schema invalid — {len(self.errors)} error(s):")
            for i, err in enumerate(self.errors, 1):
                loc = " → ".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", "")
                print(f"  {i}. [{loc}] {msg}")


def validate(project_dir: Path | str | None = None) -> ValidationReport:
    """
    Validate advocate-phenotype.yaml in the given project directory.
    Defaults to current working directory if not specified.
    Returns a ValidationReport.
    """
    project_dir = Path(project_dir or Path.cwd())
    schema_path = project_dir / "advocate-phenotype.yaml"

    if not schema_path.exists():
        return ValidationReport(
            valid=False,
            errors=[{"loc": ["advocate-phenotype.yaml"], "msg": "File not found"}],
            schema=None,
        )

    with open(schema_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    try:
        schema = CRIOSchema.model_validate(raw)
        return ValidationReport(valid=True, errors=[], schema=schema)
    except ValidationError as e:
        return ValidationReport(
            valid=False,
            errors=e.errors(),
            schema=None,
        )
