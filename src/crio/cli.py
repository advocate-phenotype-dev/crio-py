from __future__ import annotations

import json
import shutil
import subprocess
import click
from pathlib import Path


def _az_identity() -> dict | None:
    """Return {'name': ..., 'email': ...} from an active az CLI session, or None."""
    if not shutil.which("az"):
        return None
    try:
        result = subprocess.run(
            ["az", "ad", "signed-in-user", "show",
             "--query", "{name:displayName,email:mail,upn:userPrincipalName}",
             "--output", "json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        parsed = json.loads(result.stdout)
        email = parsed.get("email") or parsed.get("upn")
        return {"name": parsed.get("name"), "email": email}
    except Exception:
        return None


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


def _collect_investigator() -> tuple[str, str, str, str | None, str | None, str]:
    """Shared investigator interview. Returns (pi_name, pi_email, department, pi_orcid, staff_id, pi_role)."""
    VALID_DOMAINS = {"wakehealth.edu", "wfusm.edu", "advocatehealth.com", "advocatehealth.org"}

    click.echo(click.style("── Investigator ─────────────────────────────", fg="white"))
    az = _az_identity()
    if az:
        click.echo(
            click.style("  Resolved from Azure SSO: ", fg="cyan")
            + f"{az['name']} <{az['email']}>"
        )
    pi_name  = click.prompt(click.style("  Full name",            fg="white"),
                            default=az["name"]  if az else None)
    while True:
        pi_email = click.prompt(click.style("  Institutional email", fg="white"),
                                default=az["email"] if az else None)
        email_domain = pi_email.split("@")[-1].lower() if "@" in pi_email else ""
        if email_domain in VALID_DOMAINS:
            break
        click.echo(click.style(
            f"  ✗ {pi_email} is not an institutional address. "
            f"Must end in: {', '.join(sorted(VALID_DOMAINS))}",
            fg="red",
        ))
    department = click.prompt(click.style("  Department",          fg="white"))

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

    return pi_name, pi_email, department, pi_orcid, staff_id, pi_role


@main.command()
@click.option("--output-dir", default=".", type=click.Path())
@click.option(
    "--derive-from",
    default=None,
    metavar="UUID",
    help="UUID of upstream phenotype to derive from.",
)
def init(output_dir, derive_from):
    """Initialize a new phenotype project (interactive)."""
    from crio.init import init as _init, _load_upstream, DEFAULT_REGISTRY_PATH

    tier_labels = {
        1: "public / no restriction",
        2: "de-identified · genomics / ML",
        3: "OMOP · limited dataset · NEXUS",
        4: "identified PHI · structured",
        5: "CUI / FISMA · unstructured PHI",
    }

    # ── Load upstream if --derive-from was given ──────────────────────────
    upstream: dict | None = None
    if derive_from:
        try:
            upstream = _load_upstream(derive_from, DEFAULT_REGISTRY_PATH)
        except FileNotFoundError:
            click.echo(click.style(
                "  ! Registry not available locally — "
                "set up phenotype-library at ~/Documents/code/crio-dev/phenotype-library",
                fg="yellow",
            ))
            if not click.confirm("  Proceed without upstream pre-population?", default=True):
                click.echo("Aborted.")
                raise SystemExit(0)
            upstream = {}
        except ValueError as exc:
            click.echo(click.style(f"\n  ✗ {exc}\n", fg="red"))
            raise SystemExit(1)

    # ── Banner ────────────────────────────────────────────────────────────
    click.echo()
    click.echo(click.style("CRIO · Advocate Health Research Informatics", fg="cyan", bold=True))
    if derive_from:
        click.echo(click.style("Derived project — building on existing institutional work", fg="white"))
        click.echo()

        if upstream:
            ppv_str = (
                f"PPV {upstream['ppv'] * 100:.1f}%"
                if upstream.get("ppv") is not None
                else ""
            )
            line1 = (upstream.get("phenotype_name") or "Unknown")[:51]
            parts = [upstream.get("pi_name") or "Unknown", f"v{upstream.get('version') or '?'}"]
            if ppv_str:
                parts.append(ppv_str)
            line2 = "  ·  ".join(parts)[:51]
            line3 = f"UUID: {derive_from}"[:51]

            click.echo(f"  ┌{'─' * 55}┐")
            click.echo(f"  │  {line1:<51}  │")
            click.echo(f"  │  {line2:<51}  │")
            click.echo(f"  │  {line3:<51}  │")
            click.echo(f"  └{'─' * 55}┘")
            click.echo()

        click.echo(click.style(
            "  Fields inherited: domain · omop_aligned · clarity_required · environment",
            fg="white",
        ))
        click.echo(click.style(
            "  You will be asked to confirm or modify each inherited field.",
            fg="white",
        ))
    else:
        click.echo(click.style("New phenotype project", fg="white"))
    click.echo()

    # ── Investigator (shared) ─────────────────────────────────────────────
    pi_name, pi_email, department, pi_orcid, staff_id, pi_role = _collect_investigator()

    # ── Phenotype ─────────────────────────────────────────────────────────
    click.echo()
    click.echo(click.style("── Phenotype ────────────────────────────────", fg="white"))
    phenotype_name = click.prompt(click.style("  Phenotype name", fg="white"))

    derivation_rationale: str | None = None
    up_inc: str | None = None
    up_exc: str | None = None

    if derive_from:
        up = upstream or {}

        # Domain: inherited, no prompt
        pheno_domain = up.get("domain")
        if pheno_domain:
            click.echo(click.style(f"  Domain          {pheno_domain}  [inherited]", fg="white"))
        else:
            pheno_domain = click.prompt(
                click.style("  Domain", fg="white"),
                type=click.Choice(["condition","drug","procedure","measurement","observation"]),
            )

        description = click.prompt(click.style("  Clinical description (2–5 sentences)", fg="white"))

        # Inclusion criteria: pre-populate from upstream
        up_inc = up.get("inclusion_criteria")
        if up_inc:
            click.echo(click.style("\n  Upstream inclusion criteria:", fg="white"))
            preview = up_inc if len(up_inc) <= 300 else up_inc[:300] + "…"
            for line in preview.splitlines():
                click.echo(f"    {line}")
            if click.confirm(click.style("  Keep as-is?", fg="white"), default=True):
                inclusion_criteria = up_inc
            else:
                inclusion_criteria = click.prompt(click.style("  Inclusion criteria", fg="white"))
        else:
            inclusion_criteria = click.prompt(click.style("  Inclusion criteria", fg="white"))

        # Exclusion criteria: pre-populate from upstream
        up_exc = up.get("exclusion_criteria")
        if up_exc:
            click.echo(click.style("\n  Upstream exclusion criteria:", fg="white"))
            preview = up_exc if len(up_exc) <= 300 else up_exc[:300] + "…"
            for line in preview.splitlines():
                click.echo(f"    {line}")
            if click.confirm(click.style("  Keep as-is?", fg="white"), default=True):
                exclusion_criteria = up_exc
            else:
                exclusion_criteria = click.prompt(click.style("  Exclusion criteria", fg="white"))
        else:
            exclusion_criteria = click.prompt(
                click.style("  Exclusion criteria", fg="white"), default="none"
            )

        click.echo()
        derivation_rationale = click.prompt(
            click.style(
                "  Derivation rationale (why are you deriving from this phenotype?)",
                fg="white",
            )
        )

        # SCE / data tier: show inherited, allow override
        sce_tier    = up.get("sce_tier") or 3
        data_tier   = up.get("data_tier") or "B"
        environment = up.get("environment") or "azure_tre"
        omop_aligned    = up.get("omop_aligned")
        clarity_required = up.get("clarity_required")

        click.echo()
        click.echo(click.style("── Data access ──────────────────────────────", fg="white"))
        click.echo(
            click.style(f"→ SCE Tier {sce_tier}", fg="cyan", bold=True)
            + click.style(f"  {tier_labels.get(sce_tier, '')}", fg="white")
            + click.style("  [inherited]", fg="yellow")
        )
        click.echo(
            click.style(f"→ Data class {data_tier}", fg="cyan", bold=True)
            + click.style(f"  environment: {environment}", fg="white")
            + click.style("  [inherited]", fg="yellow")
        )

        override_raw = click.prompt(
            click.style(
                f"  SCE tier [inherited: {sce_tier}] (enter to accept, or type 1–5)",
                fg="white",
            ),
            default="",
            show_default=False,
        ).strip()
        if override_raw in {"1", "2", "3", "4", "5"}:
            sce_tier = int(override_raw)
            click.echo(click.style(f"  SCE tier overridden to {sce_tier}", fg="yellow"))

        override_dt = click.prompt(
            click.style(
                f"  Data class [inherited: {data_tier}] (enter to accept, or type A/B/C/D)",
                fg="white",
            ),
            default="",
            show_default=False,
        ).strip().upper()
        if override_dt in {"A", "B", "C", "D"}:
            data_tier = override_dt
            click.echo(click.style(f"  Data class overridden to {data_tier}", fg="yellow"))

        if omop_aligned is None:
            omop_aligned = click.confirm("  Is it OMOP-aligned?", default=True)
        if clarity_required is None:
            clarity_required = click.confirm("  Does it require Clarity direct access?", default=False)

    else:
        # Standard phenotype interview
        pheno_domain = click.prompt(
            click.style("  Domain", fg="white"),
            type=click.Choice(["condition","drug","procedure","measurement","observation"]),
        )
        description        = click.prompt(click.style("  Clinical description (2–5 sentences)", fg="white"))
        inclusion_criteria = click.prompt(click.style("  Inclusion criteria",                fg="white"))
        exclusion_criteria = click.prompt(click.style("  Exclusion criteria",                fg="white"), default="none")

        sce_tier, data_tier, omop_aligned, clarity_required, environment = _infer_sce_tier()

    # ── Governance (shared) ───────────────────────────────────────────────
    irb_number, irb_status, _ = _infer_irb(sce_tier)

    # ── Funding (shared) ──────────────────────────────────────────────────
    click.echo()
    funding_source = click.prompt(
        click.style("── Funding source (grant number or sponsor, or leave blank)", fg="white"),
        default="",
    ).strip() or None

    # ── Compute inherited vs modified (derived only) ──────────────────────
    inherited_fields: list[str] = []
    modified_fields:  list[str] = []

    if derive_from:
        up = upstream or {}
        inherited_fields = ["domain", "omop_aligned"]
        if up.get("clarity_required") is not None:
            inherited_fields.append("clarity_required")

        if up.get("sce_tier") and sce_tier != up["sce_tier"]:
            modified_fields.append("sce_tier")
        elif up.get("sce_tier"):
            inherited_fields.append("sce_tier")

        if up.get("data_tier") and data_tier != up["data_tier"]:
            modified_fields.append("data_tier")

        if up_inc is not None:
            if inclusion_criteria == up_inc:
                inherited_fields.append("inclusion_criteria")
            else:
                modified_fields.append("inclusion_criteria")

        if up_exc is not None:
            if exclusion_criteria == up_exc:
                inherited_fields.append("exclusion_criteria")
            else:
                modified_fields.append("exclusion_criteria")

    # ── Summary ───────────────────────────────────────────────────────────
    click.echo()
    click.echo(click.style("── Summary ──────────────────────────────────", fg="white"))
    click.echo(f"  Investigator  {pi_name}  ·  {pi_email}")
    click.echo(f"  Identifier    {'ORCID ' + pi_orcid if pi_orcid else 'Staff ID ' + staff_id}")
    click.echo(f"  Phenotype     {phenotype_name}  ·  {pheno_domain}")
    click.echo(f"  SCE tier      {sce_tier}  ·  data class {data_tier}  ·  {environment}")
    click.echo(f"  IRB           {irb_number or 'not required'}")

    if derive_from:
        up = upstream or {}
        up_name = up.get("phenotype_name") or "unknown"
        up_ver  = up.get("version") or "?"
        click.echo(f"  Derives from  {up_name} · v{up_ver}")
        click.echo(f"  Rationale     {derivation_rationale}")
        if inherited_fields:
            click.echo(f"  Inherited     {' · '.join(inherited_fields)}")
        if modified_fields:
            click.echo(f"  Modified      {' · '.join(modified_fields)}")

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
        domain=pheno_domain,
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
        derived_from=derive_from,
        derived_version=(upstream or {}).get("version") if derive_from else None,
        derivation_rationale=derivation_rationale,
        upstream_inclusion_criteria=up_inc,
        upstream_exclusion_criteria=up_exc,
    )


@main.command(name="list")
@click.option("--domain",    default=None, help="Filter by phenotype domain.")
@click.option("--status",    default=None, help="Filter by validation status.")
@click.option("--pi",        default=None, help="Filter by PI name (partial match).")
@click.option("--search",    default=None, help="Free-text search on name and PI.")
@click.option("--page-size", default=10,   type=int, show_default=True)
@click.option("--no-pager",  is_flag=True, default=False,
              help="Dump all results as plain text (good for piping).")
def list_cmd(domain, status, pi, search, page_size, no_pager):
    """Browse phenotypes in the registry."""
    import shutil
    from crio.list import (
        find_registry, load_registry, apply_filters, render_card,
    )

    # ── Locate registry ───────────────────────────────────────────────────
    registry_path = find_registry()
    if registry_path is None:
        click.echo(click.style(
            "\n  ✗ Registry not found. Set CRIO_LIBRARY_DIR or clone\n"
            "    phenotype-library to ~/Documents/code/crio-dev/\n",
            fg="red",
        ))
        raise SystemExit(1)

    # ── Load ──────────────────────────────────────────────────────────────
    try:
        projects = load_registry(registry_path)
    except ValueError as exc:
        click.echo(click.style(f"\n  ✗ {exc}\n", fg="red"))
        raise SystemExit(1)

    registry_dir = registry_path.parent

    # ── Filter ────────────────────────────────────────────────────────────
    filtered = apply_filters(projects, domain=domain, status=status, pi=pi, search=search)
    active_filters = {"domain": domain, "status": status, "pi": pi, "search": search}

    if not filtered:
        if projects:
            click.echo("\n  No phenotypes match your filter.\n")
        else:
            click.echo(
                "\n  No phenotypes in registry yet. Run crio init to create one.\n"
            )
        return

    # ── No-pager dump ─────────────────────────────────────────────────────
    if no_pager:
        for i, entry in enumerate(filtered, 1):
            click.echo(render_card(entry, i, len(filtered), registry_dir))
            click.echo()
        click.echo(f"  {len(filtered)} phenotype(s)")
        return

    # ── Interactive pager ─────────────────────────────────────────────────
    term_cols   = shutil.get_terminal_size((80, 24)).columns
    narrow      = term_cols < 70
    total_items = len(filtered)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    current_page = 1

    while True:
        click.clear()

        start = (current_page - 1) * page_size
        end   = start + page_size
        for i, entry in enumerate(filtered[start:end], start + 1):
            click.echo(render_card(entry, i, total_items, registry_dir, narrow=narrow))
            click.echo()

        # Status + navigation bar
        f_parts = [f"{k}: {v}" for k, v in active_filters.items() if v]
        f_desc  = f"  [{', '.join(f_parts)}]" if f_parts else ""
        click.echo(click.style(
            f"  Page {current_page} of {total_pages}"
            f"  ·  {total_items} phenotype{'s' if total_items != 1 else ''} total"
            f"{f_desc}",
            fg="white",
        ))
        click.echo(click.style(
            f"  [n] next  [p] prev  [1-{total_pages}] jump to page  [f] filter  [q] quit",
            fg="white",
        ))

        try:
            cmd = click.prompt(
                "",
                default="",
                show_default=False,
                prompt_suffix="  › ",
            ).strip().lower()
        except (click.exceptions.Abort, EOFError):
            break

        if cmd == "q":
            break
        elif cmd == "n":
            if current_page < total_pages:
                current_page += 1
        elif cmd == "p":
            if current_page > 1:
                current_page -= 1
        elif cmd == "f":
            click.echo(click.style(
                "  Filter by: domain / status / pi / free text", fg="white"
            ))
            try:
                field = click.prompt(
                    click.style("  [field or search term, blank to clear]", fg="white"),
                    default="",
                    show_default=False,
                ).strip()
            except (click.exceptions.Abort, EOFError):
                continue

            if not field:
                active_filters = {"domain": None, "status": None, "pi": None, "search": None}
            elif field == "domain":
                val = click.prompt(
                    click.style("  Domain", fg="white"),
                    type=click.Choice([
                        "condition", "drug", "procedure", "measurement", "observation"
                    ]),
                )
                active_filters["domain"] = val
            elif field == "status":
                val = click.prompt(
                    click.style("  Status", fg="white"),
                    type=click.Choice([
                        "draft", "internal_validated", "peer_reviewed", "deprecated"
                    ]),
                )
                active_filters["status"] = val
            elif field == "pi":
                val = click.prompt(click.style("  PI name (partial)", fg="white"))
                active_filters["pi"] = val
            else:
                active_filters["search"] = field

            filtered = apply_filters(
                projects,
                domain=active_filters.get("domain"),
                status=active_filters.get("status"),
                pi=active_filters.get("pi"),
                search=active_filters.get("search"),
            )
            total_items = len(filtered)
            total_pages = max(1, (total_items + page_size - 1) // page_size)
            current_page = 1

            if not filtered:
                click.echo(click.style("  No phenotypes match that filter.", fg="yellow"))
                try:
                    click.prompt("  Press enter to continue", default="", show_default=False)
                except (click.exceptions.Abort, EOFError):
                    pass
        elif cmd.isdigit():
            page_num = int(cmd)
            if 1 <= page_num <= total_pages:
                current_page = page_num


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
