import tempfile
from pathlib import Path
from crio.init import init
from crio.validate import validate


def test_validate_passes_on_valid_project():
    with tempfile.TemporaryDirectory() as tmp:
        project_dir = init(
            pi_name="Erich Huang",
            pi_orcid="0000-0002-6585-9429",
            pi_email="erich@wakehealth.edu",
            department="Research Informatics",
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
            output_dir=Path(tmp),
        )

        report = validate(project_dir)
        report.print_report()
        assert report.valid


def test_validate_fails_missing_irb_for_sce3():
    with tempfile.TemporaryDirectory() as tmp:
        project_dir = init(
            pi_name="Erich Huang",
            pi_orcid="0000-0002-6585-9429",
            pi_email="erich@wakehealth.edu",
            department="Research Informatics",
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
            irb_number=None,
            irb_status=None,
            output_dir=Path(tmp),
        )

        report = validate(project_dir)
        report.print_report()
        assert not report.valid
        print("correctly rejected missing IRB for SCE tier 3")


if __name__ == "__main__":
    test_validate_passes_on_valid_project()
    print()
    test_validate_fails_missing_irb_for_sce3()
