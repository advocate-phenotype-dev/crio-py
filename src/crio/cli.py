from __future__ import annotations

import click
from pathlib import Path


@click.group()
@click.version_option(package_name="crio")
def main():
    """CRIO — Advocate Health Research Informatics phenotype library CLI."""
    pass


@main.command()
@click.option("--pi-name",            prompt="PI full name")
@click.option("--pi-orcid",           prompt="PI ORCID (0000-0000-0000-0000)")
@click.option("--pi-email",           prompt="PI institutional email")
@click.option("--department",         prompt="Department")
@click.option("--phenotype-name",     prompt="Phenotype name")
@click.option("--domain",             prompt="Domain",
              type=click.Choice(["condition","drug","procedure","measurement","observation"]))
@click.option("--sce-tier",           prompt="SCE tier (1-5)", type=int)
@click.option("--data-tier",          prompt="Data tier",
              type=click.Choice(["A","B","C","D"]))
@click.option("--environment",        prompt="Environment",
              type=click.Choice(["azure_tre","gcp","local"]))
@click.option("--omop-aligned",       prompt="OMOP aligned?", type=bool)
@click.option("--clarity-required",   prompt="Clarity direct access required?", type=bool)
@click.option("--description",        prompt="Clinical description (2-5 sentences)")
@click.option("--inclusion-criteria", prompt="Inclusion criteria")
@click.option("--exclusion-criteria", prompt="Exclusion criteria")
@click.option("--irb-number",         default=None)
@click.option("--irb-status",         default=None,
              type=click.Choice(["active","exempt","pending"]))
@click.option("--funding-source",     default=None)
@click.option("--output-dir",         default=".", type=click.Path())
def init(pi_name, pi_orcid, pi_email, department, phenotype_name,
         domain, sce_tier, data_tier, environment, omop_aligned,
         clarity_required, description, inclusion_criteria,
         exclusion_criteria, irb_number, irb_status,
         funding_source, output_dir):
    """Initialize a new phenotype project."""
    from crio.init import init as _init

    project_dir = _init(
        pi_name=pi_name,
        pi_orcid=pi_orcid,
        pi_email=pi_email,
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
    click.echo(f"✓ Project initialized at: {project_dir}")


@main.command()
@click.option("--project-dir", default=".", type=click.Path())
@click.option("--sandbox/--no-sandbox", default=True)
def source(project_dir, sandbox):
    """Start a working session for a project."""
    from crio.source import source as _source
    _source(project_dir=Path(project_dir), sandbox=sandbox)


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
    """Validate and commit project to phenotype library."""
    from crio.publish import commit as _commit
    _commit(
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
              type=click.Choice(["ohdsi_pl","phekb"]))
def export(project_dir, target):
    """Export phenotype metadata to external registry format."""
    from crio.export import export as _export
    _export(project_dir=Path(project_dir), target=target)
