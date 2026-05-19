from __future__ import annotations

import click
from pathlib import Path


@click.group()
@click.version_option(package_name="crio")
def main():
    """CRIO — Advocate Health Research Informatics phenotype library CLI."""
    pass


def _infer_sce_tier() -> tuple[int, str, bool, bool, str | None]:
    click.echo()
    click.echo(click.style("── Data access ──────────────────────────────", fg="white"))

    identified = click.confirm(
        click.style("  Does this project use identified patient records?", fg="white"),
        default=False,
    )

    if not identified:
        uses_ehr = click.confirm(
            click.style("  Does it query EHR or OMOP data (e.g. NEXUS)?", fg="white"),
            default=True,
        )
        if not uses_ehr:
            sce_tier    = 2
            data_tier   = "A"
            omop        = click.confirm("  Is it OMOP-aligned?", default=True)
            clarity     = False
            environment = "gcp"
        else:
            sce_tier    = 3
            data_tier   = "B"
            omop        = True
            clarity     = False
            environment = "azure_tre"
    else:
        unstructured = click.confirm(
            click.style(
                "  Does it require unstructured notes, Clarity direct, or CUI-regulated data?",
                fg="white",
            ),
            default=False,
        )
        if unstructured:
            sce_tier    = 5
            data_tier   = "D"
            omop        = False
            clarity     = True
            environment = "azure_tre"
        else:
            sce_tier    = 4
            data_tier   = "C"
            omop        = click.confirm("  Is it OMOP-aligned?", default=True)
            clarity     = False
            environment = "azure_tre"

    tier_labels = {
        1: "public / no restriction",
        2: "de-identified · genomics / ML",
        3: "OMOP · limited dataset · NEXUS",
        4: "identified PHI · structured",
        5: "CUI / FISMA · unstructured PHI",
    }
    click.echo()
    click.echo(
        click.style(f"→ SCE Tier {sce_tier}", fg="cyan", bold=True)
        + click.style(f"  {tier_labels[sce_tier]}", fg="white")
    )
    click.echo(
        click.style(f"→ Data class {data_tier}", fg="cyan", bold=True)
        + click.style(f"  environment: {environment}", fg="white")
    )

    override_raw = click.prompt(
        click.style(
            "  Override SCE tier? [enter to accept, or type 1–5]",
            fg="white",
        ),
        default="",
        show_default=False,
    ).strip()

    if override_raw in {"1", "2", "3", "4", "5"}:
        sce_tier = int(override_raw)
        click.echo(click.style(f"  SCE tier overridden to {sce_tier}", fg="yellow"))

    return sce_tier, data_tier, omop, clarity, environment


def _infer_irb(sce_tier: int) -> tuple[str | None, str | None, bool]:
    click.echo()
    click.echo(click.style("── Governance ───────────────────────────────", fg="white"))

    is_research = click.confirm(
        click.style(
            "  Is this a research project (vs. operational / quality analytics)?",
            fg="white",
        ),
        default=False,
    )

    if not is_research:
        click.echo(click.style("→ Operational pathway — no IRB required", fg="cyan"))
        return None, None, False

    if sce_tier >= 3:
        click.echo(
            click.style(f"→ Research at SCE tier {sce_tier} — IRB required", fg="cyan")
        )
        irb_number = click.prompt(click.style("  IRB number", fg="white"))
        irb_status = click.prompt(
            click.style("  IRB status", fg="white"),
            type=click.Choice(["active", "exempt", "pending"]),
            default="active",
        )
        return irb_number, irb_status, True

    click.echo(
        click.style(f"→ Research at SCE tier {sce_tier} — IRB recommended but not enforced", fg="yellow")
    )
    irb_number = click.prompt(
        click.style("  IRB number (or leave blank)", fg="white"),
        default="",
    ).strip() or None
    irb_status = "active" if irb_number else None
    return irb_number, irb_status, bool(irb_number)


@main.command()
@click.option("--output-dir", default=".", type=click.Path())
def init(output_dir):
    """Initialize a new phenotype project (interactive)."""
    from crio.init import init as _init

    click.echo()
    click.echo(click.style("CRIO · Advocate Health Research Informatics", fg="cyan", bold=True))
    click.echo(click.style("New phenotype project", fg="white"))
    click.echo()

    click.echo(click.style("── Investigator ─────────────────────────────", fg="white"))
    pi_name  = click.prompt(click.style("  Full name",            fg="white"))
    pi_email = click.prompt(click.style("  Institutional email",  fg="white"))
    department = click.prompt(click.style("  Department",         fg="white"))

    click.echo()
    has_orcid = click.confirm(
        click.style("  Do you have an ORCID iD?", fg="white"), default=True
    )
    pi_orcid = None
    staff_id = None
    if has_orcid:
        pi_orcid = click.prompt(click.style("  ORCID (0000-0000-0000-0000)", fg="white"))
        pi_role  = click.prompt(
            click.style("  Role", fg="white"),
            type=click.Choice(["researcher","informaticist","data_scientist","quality_analyst","clinical_ops"]),
            default="researcher",
        )
    else:
        staff_id = click.prompt(click.style("  Advocate staff ID", fg="white"))
        pi_role  = click.prompt(
            click.style("  Role", fg="white"),
            type=click.Choice(["researcher","informaticist","data_scientist","quality_analyst","clinical_ops"]),
            default="data_scientist",
        )

    click.echo()
    click.echo(click.style("── Phenotype ────────────────────────────────", fg="white"))
    phenotype_name     = click.prompt(click.style("  Phenotype name",                    fg="white"))
    domain             = click.prompt(
        click.style("  Domain", fg="white"),
        type=click.Choice(["condition","drug","procedure","measurement","observation"]),
    )
    description        = click.prompt(click.style("  Clinical description (2–5 sentences)", fg="white"))
    inclusion_criteria = click.prompt(click.style("  Inclusion criteria",                fg="white"))
    exclusion_criteria = click.prompt(click.style("  Exclusion criteria",                fg="white"), default="none")

    sce_tier, data_tier, omop_aligned, clarity_required, environment = _infer_sce_tier()
    irb_number, irb_status, _ = _infer_irb(sce_tier)

    click.echo()
    funding_source = click.prompt(
        click.style("── Funding source (grant number or sponsor, or leave blank)", fg="white"),
        default="",
    ).strip() or None

    click.echo()
    click.echo(click.style("── Summary ──────────────────────────────────", fg="white"))
    click.echo(f"  Investigator  {pi_name}  ·  {pi_email}")
    click.echo(f"  Identifier    {'ORCID ' + pi_orcid if pi_orcid else 'Staff ID ' + staff_id}")
    click.echo(f"  Phenotype     {phenotype_name}  ·  {domain}")
    click.echo(f"  SCE tier      {sce_tier}  ·  data class {data_tier}  ·  {environment}")
    click.echo(f"  IRB           {irb_number or 'not required'}")
    click.echo()

    if not click.confirm(click.style("  Initialize project?", fg="white"), default=True):
        click.echo("Aborted.")
        raise SystemExit(0)

    click.echo()
    _init(
        pi_name=pi_name,
        pi_orcid=pi_orcid,
        pi_email=pi_email,
        staff_id=staff_id,
        pi_role=pi_role,
        department=department,
        phenotype_name=phenotype_name,
        domain=domain,
        sce_tier=sce_tier,
        data_tier=data_tier,
        environment=environment,
        omop_aligned=omop_aligned,
        clarity_required=clarity_required,
        description=description,
        inclusion_criteria=inclusion_criteria,
        exclusion_criteria=exclusion_criteria,
        irb_number=irb_number,
        irb_status=irb_status,
        funding_source=funding_source,
        output_dir=Path(output_dir),
    )


@main.command()
@click.option("--project-dir", default=".", type=click.Path())
@click.option("--sandbox/--no-sandbox", default=True)
def source(project_dir, sandbox):
    """Start a working session for a project."""
    from crio.source import source as _source
    try:
        _source(project_dir=Path(project_dir) if project_dir else None, sandbox=sandbox)
    except FileNotFoundError as e:
        click.echo(f"\n✗ {e}\n")
        raise SystemExit(1)


@main.command()
@click.option("--project-dir", default=".", type=click.Path())
def validate(project_dir):
    """Validate advocate-phenotype.yaml."""
    from crio.validate import validate as _validate
    report = _validate(project_dir=Path(project_dir))
    report.print_report()
    raise SystemExit(0 if report.valid else 1)


@main.command()
@click.option("--project-dir",  default=".",  type=click.Path())
@click.option("--library-dir",  required=True, type=click.Path())
@click.option("--message", "-m", required=True)
@click.option("--sandbox/--no-sandbox", default=True)
def publish(project_dir, library_dir, message, sandbox):
    """Validate and publish project to phenotype library."""
    from crio.publish import publish as _publish
    _publish(
        project_dir=Path(project_dir),
        library_dir=Path(library_dir),
        message=message,
        sandbox=sandbox,
    )


@main.command()
@click.option("--project-dir", default=".", type=click.Path())
@click.option("--sandbox/--no-sandbox", default=True)
def deposit(project_dir, sandbox):
    """Submit phenotype for deposit review."""
    from crio.deposit import deposit as _deposit
    success = _deposit(project_dir=Path(project_dir), sandbox=sandbox)
    raise SystemExit(0 if success else 1)


@main.command()
@click.option("--project-dir", default=".", type=click.Path())
@click.option("--target", default="ohdsi_pl",
              type=click.Choice(["ohdsi_pl", "phekb", "ncct_trial_ready"]))
def export(project_dir, target):
    """Export phenotype metadata to external registry format."""
    from crio.export import export as _export
    _export(project_dir=Path(project_dir), target=target)
