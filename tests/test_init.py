import tempfile
from pathlib import Path

import yaml
import pytest

from crio.init import init, _load_upstream


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


# ── _load_upstream tests ──────────────────────────────────────────────────────

def _make_registry(tmp: Path, entries: list[dict]) -> Path:
    registry_path = tmp / "registry.yaml"
    with open(registry_path, "w") as f:
        yaml.dump({"projects": entries}, f)
    return registry_path


def _make_project_yaml(tmp: Path, uuid: str, phenotype: dict, compute: dict, investigator: dict):
    project_dir = tmp / "projects" / uuid
    project_dir.mkdir(parents=True)
    schema = {
        "project": {"id": uuid, "created": "2026-01-01T00:00:00+00:00", "updated": "2026-01-01T00:00:00+00:00"},
        "investigator": investigator,
        "institution": {"department": "Research"},
        "compute": compute,
        "phenotype": phenotype,
    }
    with open(project_dir / "advocate-phenotype.yaml", "w") as f:
        yaml.dump(schema, f)


def test_load_upstream_full_project_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        registry_path = _make_registry(tmp, [{
            "id": uuid,
            "pi_name": "Dr. Test",
            "phenotype_name": "Test Phenotype",
            "domain": "condition",
            "validation_status": "internal_validated",
            "sce_tier": 3,
        }])

        _make_project_yaml(
            tmp, uuid,
            phenotype={
                "name": "Test Phenotype",
                "version": "1.2.0",
                "domain": "condition",
                "omop_aligned": False,
                "clarity_required": False,
                "inclusion_criteria": "Patients with X",
                "exclusion_criteria": "Patients under 18",
                "validation_status": "internal_validated",
                "ppv": 0.92,
            },
            compute={"sce_tier": 3, "data_tier": "B", "environment": "azure_tre"},
            investigator={"pi_name": "Dr. Test", "pi_email": "test@advocatehealth.com"},
        )

        result = _load_upstream(uuid, registry_path)

        assert result["phenotype_name"] == "Test Phenotype"
        assert result["version"] == "1.2.0"
        assert result["domain"] == "condition"
        assert result["omop_aligned"] is False
        assert result["clarity_required"] is False
        assert result["sce_tier"] == 3
        assert result["data_tier"] == "B"
        assert result["environment"] == "azure_tre"
        assert result["inclusion_criteria"] == "Patients with X"
        assert result["exclusion_criteria"] == "Patients under 18"
        assert result["ppv"] == pytest.approx(0.92)


def test_load_upstream_fallback_registry_only():
    """Falls back to registry-level data when project YAML is absent."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        registry_path = _make_registry(tmp, [{
            "id": uuid,
            "pi_name": "Dr. Test",
            "phenotype_name": "Test Phenotype",
            "domain": "condition",
            "validation_status": "draft",
            "sce_tier": 2,
        }])

        result = _load_upstream(uuid, registry_path)

        assert result["phenotype_name"] == "Test Phenotype"
        assert result["domain"] == "condition"
        assert result["sce_tier"] == 2
        assert result["version"] is None
        assert result["omop_aligned"] is None
        assert result["inclusion_criteria"] is None


def test_load_upstream_uuid_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        registry_path = _make_registry(tmp, [{"id": "other-uuid", "phenotype_name": "Other"}])

        with pytest.raises(ValueError, match="not found in registry"):
            _load_upstream("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", registry_path)


def test_load_upstream_registry_not_found():
    with pytest.raises(FileNotFoundError):
        _load_upstream("some-uuid", Path("/nonexistent/path/registry.yaml"))


# ── init() derived tests ──────────────────────────────────────────────────────

def test_init_derived_schema_fields():
    """init() with derived_from writes derived_from, derived_version,
    derivation_rationale, and inherited_criteria to the output YAML."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        registry_path = _make_registry(tmp, [{
            "id": uuid,
            "pi_name": "Dr. Upstream",
            "phenotype_name": "Upstream Phenotype",
            "domain": "condition",
            "validation_status": "internal_validated",
            "sce_tier": 3,
        }])

        upstream_inc = "Patients with condition X documented in EHR"
        upstream_exc = "Patients under 18 years old"

        _make_project_yaml(
            tmp, uuid,
            phenotype={
                "name": "Upstream Phenotype",
                "version": "1.0.0",
                "domain": "condition",
                "omop_aligned": False,
                "clarity_required": False,
                "inclusion_criteria": upstream_inc,
                "exclusion_criteria": upstream_exc,
                "validation_status": "internal_validated",
                "ppv": None,
            },
            compute={"sce_tier": 3, "data_tier": "B", "environment": "azure_tre"},
            investigator={"pi_name": "Dr. Upstream", "pi_email": "upstream@advocatehealth.com"},
        )

        upstream = _load_upstream(uuid, registry_path)

        output_dir = tmp / "output"
        output_dir.mkdir()

        project_dir = init(
            pi_name="New Researcher",
            pi_orcid="0000-0002-6585-9429",
            pi_email="new@wakehealth.edu",
            department="Research Informatics",
            phenotype_name="Derived Phenotype",
            domain="condition",
            sce_tier=3,
            data_tier="B",
            environment="azure_tre",
            omop_aligned=False,
            clarity_required=False,
            description="A derived version of the upstream phenotype.",
            inclusion_criteria=upstream_inc,      # unchanged — should be "inherited"
            exclusion_criteria="Modified exclusion criteria",  # changed — "modified"
            irb_number="IRB-2026-002",
            irb_status="active",
            output_dir=output_dir,
            derived_from=uuid,
            derived_version=upstream["version"],
            derivation_rationale="Extending to include pediatric population.",
            upstream_inclusion_criteria=upstream_inc,
            upstream_exclusion_criteria=upstream_exc,
        )

        with open(project_dir / "advocate-phenotype.yaml") as f:
            schema = yaml.safe_load(f)

        # project block
        assert schema["project"]["derived_from"] == uuid
        assert schema["project"]["derived_version"] == "1.0.0"
        assert schema["project"]["derivation_rationale"] == "Extending to include pediatric population."

        # inherited_criteria
        inherited = schema["phenotype"]["inherited_criteria"]
        assert inherited is not None
        assert len(inherited) == 2

        inc_entry = next(x for x in inherited if x["field"] == "inclusion_criteria")
        exc_entry = next(x for x in inherited if x["field"] == "exclusion_criteria")

        assert inc_entry["status"] == "inherited"
        assert inc_entry["from_version"] == "1.0.0"

        assert exc_entry["status"] == "modified"
        assert exc_entry["from_version"] == "1.0.0"


def test_init_derived_inherited_criteria_new_when_no_upstream():
    """When upstream criteria are None, inherited_criteria status should be 'new'."""
    with tempfile.TemporaryDirectory() as tmp:
        project_dir = init(
            pi_name="Researcher",
            pi_orcid="0000-0002-6585-9429",
            pi_email="res@wakehealth.edu",
            department="Research",
            phenotype_name="New Derived",
            domain="condition",
            sce_tier=3,
            data_tier="B",
            environment="azure_tre",
            omop_aligned=False,
            clarity_required=False,
            description="A derived phenotype with no upstream criteria data.",
            inclusion_criteria="Patients with Y",
            exclusion_criteria="Patients under 18",
            irb_number="IRB-2026-003",
            irb_status="active",
            output_dir=Path(tmp),
            derived_from="some-uuid",
            derived_version=None,
            derivation_rationale="Rationale here.",
            upstream_inclusion_criteria=None,
            upstream_exclusion_criteria=None,
        )

        with open(project_dir / "advocate-phenotype.yaml") as f:
            schema = yaml.safe_load(f)

        inherited = schema["phenotype"]["inherited_criteria"]
        assert all(x["status"] == "new" for x in inherited)


if __name__ == "__main__":
    test_init_creates_structure()
    print("all assertions passed")
