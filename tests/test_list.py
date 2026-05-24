from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import click
import yaml
import pytest
from click.testing import CliRunner

from crio.cli import main
from crio.list import apply_filters, load_registry, render_card


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_registry(path: Path, entries: list[dict]) -> None:
    with open(path, "w") as f:
        yaml.dump({"generated": "2026-05-23T00:00:00+00:00", "projects": entries}, f)


SAMPLE = [
    {
        "id": "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb",
        "pi_name": "Dr. Alice Smith",
        "phenotype_name": "Acute MI Phenotype",
        "domain": "condition",
        "validation_status": "internal_validated",
        "deposit_eligible": True,
        "credit_granted": False,
        "sce_tier": 3,
        "updated": "2026-05-01T00:00:00+00:00",
    },
    {
        "id": "cccccccc-4444-5555-6666-dddddddddddd",
        "pi_name": "Dr. Bob Jones",
        "phenotype_name": "Type 2 Diabetes Screening",
        "domain": "condition",
        "validation_status": "draft",
        "deposit_eligible": False,
        "credit_granted": False,
        "sce_tier": 2,
        "updated": "2026-04-15T00:00:00+00:00",
    },
    {
        "id": "eeeeeeee-7777-8888-9999-ffffffffffff",
        "pi_name": "Dr. Alice Smith",
        "phenotype_name": "Metformin Adherence Study",
        "domain": "drug",
        "validation_status": "internal_validated",
        "deposit_eligible": True,
        "credit_granted": True,
        "sce_tier": 3,
        "updated": "2026-03-20T00:00:00+00:00",
    },
]


# ── Unit tests for list helpers ───────────────────────────────────────────────

def test_load_registry_parses_entries():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "registry.yaml"
        _write_registry(path, SAMPLE)
        entries = load_registry(path)
        assert len(entries) == 3
        assert entries[0]["phenotype_name"] == "Acute MI Phenotype"


def test_load_registry_empty():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "registry.yaml"
        _write_registry(path, [])
        assert load_registry(path) == []


def test_load_registry_malformed_raises():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "registry.yaml"
        path.write_text(": : bad yaml [[\n")
        with pytest.raises(ValueError, match="Malformed"):
            load_registry(path)


def test_apply_filters_domain():
    result = apply_filters(SAMPLE, domain="drug")
    assert len(result) == 1
    assert result[0]["phenotype_name"] == "Metformin Adherence Study"


def test_apply_filters_status():
    result = apply_filters(SAMPLE, status="draft")
    assert len(result) == 1
    assert result[0]["phenotype_name"] == "Type 2 Diabetes Screening"


def test_apply_filters_pi():
    result = apply_filters(SAMPLE, pi="alice")
    assert len(result) == 2
    names = {e["phenotype_name"] for e in result}
    assert "Acute MI Phenotype" in names
    assert "Metformin Adherence Study" in names


def test_apply_filters_search_name_and_pi():
    # Matches on phenotype_name
    result = apply_filters(SAMPLE, search="diabetes")
    assert len(result) == 1
    assert result[0]["phenotype_name"] == "Type 2 Diabetes Screening"

    # Matches on pi_name
    result = apply_filters(SAMPLE, search="bob")
    assert len(result) == 1
    assert result[0]["pi_name"] == "Dr. Bob Jones"


def test_apply_filters_combined_and_semantics():
    # domain=condition AND pi=alice → 1 result (not drug entry)
    result = apply_filters(SAMPLE, domain="condition", pi="alice")
    assert len(result) == 1
    assert result[0]["phenotype_name"] == "Acute MI Phenotype"


def test_render_card_contains_key_fields():
    entry = SAMPLE[0]
    card = render_card(entry, 1, 3)
    plain = click.unstyle(card) if hasattr(click, "unstyle") else card
    assert "Acute MI Phenotype" in plain
    assert "Dr. Alice Smith" in plain
    assert "1 / 3" in plain
    assert "internal_validated" in plain
    assert "SCE tier 3" in plain
    assert "domain: condition" in plain


# ── CLI integration tests ──────────────────────────────────────────────────────

def _invoke_list(tmp: Path, extra_args: list[str] | None = None) -> tuple[int, str]:
    runner = CliRunner()
    args   = ["list", "--no-pager"] + (extra_args or [])
    result = runner.invoke(main, args, env={"CRIO_LIBRARY_DIR": str(tmp)})
    return result.exit_code, result.output


def test_cli_list_shows_all_phenotype_names():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _write_registry(tmp / "registry.yaml", SAMPLE)

        code, out = _invoke_list(tmp)

        assert code == 0
        assert "Acute MI Phenotype" in out
        assert "Type 2 Diabetes Screening" in out
        assert "Metformin Adherence Study" in out


def test_cli_list_domain_filter():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _write_registry(tmp / "registry.yaml", SAMPLE)

        code, out = _invoke_list(tmp, ["--domain", "drug"])

        assert code == 0
        assert "Metformin Adherence Study" in out
        assert "Acute MI Phenotype" not in out
        assert "Type 2 Diabetes Screening" not in out


def test_cli_list_search_filter_name_and_pi():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _write_registry(tmp / "registry.yaml", SAMPLE)

        # Search by phenotype name fragment
        code, out = _invoke_list(tmp, ["--search", "diabetes"])
        assert code == 0
        assert "Type 2 Diabetes Screening" in out
        assert "Acute MI Phenotype" not in out

        # Search by PI name fragment
        code, out = _invoke_list(tmp, ["--search", "alice"])
        assert code == 0
        assert "Acute MI Phenotype" in out
        assert "Metformin Adherence Study" in out
        assert "Type 2 Diabetes Screening" not in out


def test_cli_list_empty_registry():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _write_registry(tmp / "registry.yaml", [])

        code, out = _invoke_list(tmp)

        assert code == 0
        assert "No phenotypes" in out


def test_cli_list_no_results_after_filter():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _write_registry(tmp / "registry.yaml", SAMPLE)

        code, out = _invoke_list(tmp, ["--domain", "observation"])

        assert code == 0
        assert "No phenotypes match" in out


def test_cli_list_registry_not_found():
    import crio.list as crio_list_module

    runner = CliRunner()
    with patch.object(crio_list_module, "find_registry", return_value=None):
        result = runner.invoke(main, ["list", "--no-pager"])

    assert result.exit_code != 0
    assert "Registry not found" in result.output


def test_cli_list_pi_filter():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _write_registry(tmp / "registry.yaml", SAMPLE)

        code, out = _invoke_list(tmp, ["--pi", "Bob"])

        assert code == 0
        assert "Type 2 Diabetes Screening" in out
        assert "Acute MI Phenotype" not in out


# Allow running directly
if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
