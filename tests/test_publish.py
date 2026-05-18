import tempfile
import yaml
from pathlib import Path
from crio.init import init
from crio.publish import publish


def test_commit_sandbox():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # init a project
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
            output_dir=tmp,
        )

        # init a mock phenotype-library repo
        import git
        library_dir = tmp / "phenotype-library"
        library_dir.mkdir()
        git.Repo.init(library_dir)

        # commit in sandbox mode
        publish(
            project_dir=project_dir,
            library_dir=library_dir,
            message="Initial commit",
            sandbox=True,
        )

        # verify project landed in library
        import yaml
        schema = yaml.safe_load((project_dir / "advocate-phenotype.yaml").read_text())
        project_id = schema["project"]["id"]
        assert (library_dir / "projects" / project_id / "advocate-phenotype.yaml").exists()
        assert (library_dir / "registry.yaml").exists()

        # verify registry entry
        with open(library_dir / "registry.yaml") as f:
            registry = yaml.safe_load(f)

        assert len(registry["projects"]) == 1
        assert registry["projects"][0]["id"] == project_id
        print(f"✓ Registry entry: {registry['projects'][0]['phenotype_name']}")
        print("all assertions passed")


if __name__ == "__main__":
    test_commit_sandbox()
