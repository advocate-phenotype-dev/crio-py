from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml


def deposit(
    project_dir=None,
    library_dir=None,
    sandbox: bool = True,
) -> bool:
    from crio.validate import validate

    project_dir = Path(project_dir or Path.cwd())
    schema_path = project_dir / "advocate-phenotype.yaml"

    report = validate(project_dir)
    if not report.valid:
        print("Deposit aborted — schema invalid:")
        report.print_report()
        return False

    schema = report.schema

    if not schema.contribution.deposit_eligible:
        print("Deposit not eligible.")
        print("  Phenotype must be at least internal_validated status")
        print("  and have description, inclusion, and exclusion criteria populated.")
        return False

    if schema.contribution.deposit_submitted:
        print("Deposit already submitted.")
        return False

    with open(schema_path) as f:
        raw = yaml.safe_load(f)

    now = datetime.now(timezone.utc).isoformat()
    raw["contribution"]["deposit_submitted"] = True
    raw["contribution"]["deposit_date"] = now
    raw["project"]["updated"] = now

    with open(schema_path, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, sort_keys=False)

    if sandbox:
        print("✓ Deposit submitted (sandbox)")
        print(f"  Phenotype: {schema.phenotype.name}")
        print(f"  Version:   {schema.phenotype.version}")
        print(f"  PI ORCID:  {schema.investigator.pi_orcid}")
        print("  Clearinghouse notified: [sandbox mock]")
    else:
        raise NotImplementedError("Clearinghouse API endpoint not yet configured.")

    return True
