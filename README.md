# crio-py

Python library for Advocate Health / Wake Forest University School of Medicine
research informatics infrastructure. Provides session management, schema
validation, and phenotype library contribution tooling for investigators
working in secure computing environments.

## Installation

    pip install crio

For local development:

    git clone https://github.com/advocate-phenotype-dev/crio-py
    cd crio-py
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .

## Quick start

    import crio

    project_dir = crio.init(
        pi_name="Jane Reyes",
        pi_orcid="0000-0000-0000-0000",
        pi_email="jane.reyes@advocatehealth.org",
        department="Cardiovascular Epidemiology",
        phenotype_name="Heart failure with reduced EF",
        domain="condition",
        sce_tier=3,
        data_tier="B",
        environment="azure_tre",
        omop_aligned=False,
        clarity_required=True,
        description="Identifies patients with HFrEF based on EF < 40%.",
        inclusion_criteria="EF < 40% on echocardiogram; ICD-10 I50.x",
        exclusion_criteria="Age < 18; no qualifying echo within 2 years",
        irb_number="IRB-2026-001",
        irb_status="active",
    )

    crio.source(project_dir, sandbox=True)
    report = crio.validate(project_dir)
    report.print_report()
    crio.publish(project_dir=project_dir, library_dir="../phenotype-library", message="v0.1", sandbox=True)
    crio.export(project_dir, target="ohdsi_pl")
    crio.deposit(project_dir, sandbox=True)

## CLI

    crio init
    crio validate --project-dir .
    crio source --project-dir .
    crio publish --project-dir . --library-dir ../phenotype-library -m "Initial commit"
    crio export --project-dir . --target ohdsi_pl
    crio deposit --project-dir .

## Schema enforcement

- Institutional email required (wakehealth.edu, wfusm.edu, advocatehealth.org/com)
- ORCID iD format validated
- IRB number and status required for SCE tier 3+
- Semantic versioning enforced
- Deposit eligibility computed automatically from validation status and field completeness

## External registries

OMOP-aligned phenotypes export to OHDSI Phenotype Library (--target ohdsi_pl)
or PheKB (--target phekb).

## Phenotype library

Committed projects are tracked at:
https://github.com/advocate-phenotype-dev/phenotype-library

## Status

Active prototype. Azure TRE credential endpoint not yet connected.
Run with sandbox=True for local development.

## License

Apache 2.0
