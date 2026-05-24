from __future__ import annotations

import os
import shutil
from pathlib import Path

import click
import yaml


# Module-level enrichment cache (short-lived per CLI invocation).
_enrichment_cache: dict[str, dict] = {}


def find_registry() -> Path | None:
    """Locate registry.yaml in standard locations.

    Search order:
    1. $CRIO_LIBRARY_DIR/registry.yaml
    2. ~/Documents/code/crio-dev/phenotype-library/registry.yaml
    3. Walk upward from cwd looking for phenotype-library/registry.yaml
    """
    env_dir = os.environ.get("CRIO_LIBRARY_DIR")
    if env_dir:
        p = Path(env_dir) / "registry.yaml"
        if p.exists():
            return p
        # Env var was set but file not found — don't fall through to defaults
        # so that tests (and users) can control the lookup unambiguously.
        return None

    default = (
        Path.home()
        / "Documents"
        / "code"
        / "crio-dev"
        / "phenotype-library"
        / "registry.yaml"
    )
    if default.exists():
        return default

    current = Path.cwd()
    for _ in range(12):
        candidate = current / "phenotype-library" / "registry.yaml"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def load_registry(path: Path) -> list[dict]:
    """Parse registry.yaml and return the projects list.

    Raises ValueError on YAML parse errors.
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed registry YAML at {path}: {exc}") from exc

    if not isinstance(data, dict):
        return []

    projects = data.get("projects") or []
    return [p for p in projects if isinstance(p, dict)]


def _load_enrichment(registry_dir: Path, uuid: str) -> dict:
    """Load extra fields (version, ppv, derived_from, irb_number) from project YAML.

    Returns {} on missing file or any parse error.
    """
    if uuid in _enrichment_cache:
        return _enrichment_cache[uuid]

    project_yaml = registry_dir / "projects" / uuid / "advocate-phenotype.yaml"
    if not project_yaml.exists():
        _enrichment_cache[uuid] = {}
        return {}

    try:
        with open(project_yaml) as f:
            schema = yaml.safe_load(f)
        if not isinstance(schema, dict):
            _enrichment_cache[uuid] = {}
            return {}

        phenotype = schema.get("phenotype") or {}
        project   = schema.get("project") or {}
        institution = schema.get("institution") or {}

        result = {
            "version":    phenotype.get("version"),
            "ppv":        phenotype.get("ppv"),
            "derived_from": project.get("derived_from"),
            "irb_number": institution.get("irb_number"),
        }
    except Exception:
        result = {}

    _enrichment_cache[uuid] = result
    return result


def apply_filters(
    projects: list[dict],
    domain:   str | None = None,
    status:   str | None = None,
    pi:       str | None = None,
    search:   str | None = None,
) -> list[dict]:
    """Return entries matching all supplied filters (AND semantics)."""
    result = projects
    if domain:
        result = [p for p in result if str(p.get("domain") or "").lower() == domain.lower()]
    if status:
        result = [
            p for p in result
            if str(p.get("validation_status") or "").lower() == status.lower()
        ]
    if pi:
        result = [p for p in result if pi.lower() in str(p.get("pi_name") or "").lower()]
    if search:
        s = search.lower()
        result = [
            p for p in result
            if s in str(p.get("phenotype_name") or "").lower()
            or s in str(p.get("pi_name") or "").lower()
        ]
    return result


def _status_color(status: str) -> str:
    return {
        "internal_validated": "green",
        "peer_reviewed":      "green",
        "draft":              "yellow",
        "deprecated":         "red",
    }.get(status, "white")


def render_card(
    entry:        dict,
    idx:          int,
    total:        int,
    registry_dir: Path | None = None,
    narrow:       bool = False,
) -> str:
    """Return a rendered card string for one registry entry."""
    INNER = 63  # chars between │ and │

    # ── Compact format for narrow terminals ──────────────────────────────
    if narrow:
        name   = (entry.get("phenotype_name") or "?")[:40]
        status = entry.get("validation_status") or "?"
        uid    = str(entry.get("id") or "")[:8]
        return (
            f"  {idx:>3}. "
            + click.style(name, bold=True)
            + "  "
            + click.style(f"[{status}]", fg=_status_color(status))
            + click.style(f"  {uid}…", fg="bright_black")
        )

    # ── Enrich from project YAML ──────────────────────────────────────────
    uuid_str = str(entry.get("id") or "")
    enriched: dict = {}
    if registry_dir and uuid_str:
        enriched = _load_enrichment(registry_dir, uuid_str)

    name       = entry.get("phenotype_name") or "Unknown"
    pi_name    = entry.get("pi_name") or ""
    sce_tier   = entry.get("sce_tier")
    domain     = entry.get("domain") or ""
    status     = entry.get("validation_status") or ""
    deposit    = entry.get("deposit_eligible")
    updated    = str(entry.get("updated") or "")[:10]

    version      = enriched.get("version")
    ppv          = enriched.get("ppv")
    derived_from = enriched.get("derived_from")

    content_w = INNER - 2  # 61 usable chars per content line

    def _line(styled: str) -> str:
        """Wrap styled content in card border, padded to INNER width."""
        vlen   = len(click.unstyle(styled))
        spaces = max(0, content_w - vlen)
        return f"  │  {styled}{' ' * spaces}│"

    # Line 1: phenotype name (left) + page position (right)
    page_str  = f"{idx} / {total}"
    name_max  = content_w - len(page_str) - 1
    name_trunc = name[:name_max]
    l1 = click.style(f"{name_trunc:<{name_max}} {page_str}", fg="white", bold=True)

    # Line 2: PI name
    l2 = click.style(pi_name[:content_w], fg="white")

    # Line 3: UUID short · version · date
    short_uuid = f"{uuid_str[:8]}…" if uuid_str else "?"
    parts3: list[str] = [f"UUID: {short_uuid}"]
    if version:
        parts3.append(f"v{version}")
    if updated:
        parts3.append(updated)
    l3 = click.style("  ·  ".join(parts3)[:content_w], fg="bright_black")

    # Line 4: PPV · validation_status (colored) · SCE tier
    parts4_styled: list[str] = []
    if ppv is not None:
        parts4_styled.append(click.style(f"PPV {ppv * 100:.1f}%", fg="white"))
    parts4_styled.append(click.style(status, fg=_status_color(status)))
    if sce_tier is not None:
        parts4_styled.append(click.style(f"SCE tier {sce_tier}", fg="white"))
    sep = click.style("  ·  ", fg="white")
    l4 = sep.join(parts4_styled)

    # Line 5: domain · deposit_eligible [· ↳ derived from UUID if it fits]
    dep_color   = "green" if deposit else "bright_black"
    dep_str     = "true" if deposit else "false"
    base5_plain = f"domain: {domain}  ·  deposit_eligible: {dep_str}"
    base5_styled = (
        click.style(f"domain: {domain}", fg="white")
        + click.style("  ·  ", fg="white")
        + click.style(f"deposit_eligible: {dep_str}", fg=dep_color)
    )

    if derived_from:
        short_df   = str(derived_from)[:8] + "…"
        derived_seg = f"  ·  ↳ {short_df}"
        if len(base5_plain) + len(derived_seg) <= content_w:
            base5_styled += click.style(derived_seg, fg="cyan")

    l5 = base5_styled

    border = f"  ┌{'─' * INNER}┐"
    bottom = f"  └{'─' * INNER}┘"

    return "\n".join([border, _line(l1), _line(l2), _line(l3), _line(l4), _line(l5), bottom])
