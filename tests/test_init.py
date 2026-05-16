import tempfile
from pathlib import Path
from crio.init import init


def test_init_creates_structure():
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
            omop_aligned=True,
            clarity_required=False,
            description="Identifies patients with HFrEF based on EF < 40%.",
            inclusion_criteria="EF < 40% on echocardiogram; ICD-10 I50.x",
            exclusion_criteria="Age < 18; no qualifying echo within 2 years",
            irb_number="IRB-2026-001",
            irb_status="active",
            output_dir=Path(tmp),
        )

        assert project_dir.exists()
        assert (project_dir / "advocate-phenotype.yaml").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / ".gitignore").exists()
        assert (project_dir / "src" / "cohort_definition").exists()
        assert (project_dir / ".advocate").exists()
        print(f"Project created at: {project_dir}")


if __name__ == "__main__":
    test_init_creates_structure()
    print("all assertions passed")
