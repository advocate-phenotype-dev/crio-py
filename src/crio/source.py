from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path


ADVOCATE_DIR = ".advocate"
SESSION_LOCK = ".advocate/session.lock"

SANDBOX_CREDENTIALS = {
    "mode": "sandbox",
    "sce_tier": None,
    "environment": "local",
    "library_remote": "https://github.com/advocate-phenotype-dev/phenotype-library.git",
    "token": "sandbox-mock-token",
    "issued_at": None,
    "expires_at": None,
}


def source(
    project_dir: "Path | str | None" = None,
    sandbox: bool = True,
) -> dict:
    from crio.validate import validate

    project_dir = Path(project_dir or Path.cwd())
    advocate_dir = project_dir / ADVOCATE_DIR
    advocate_dir.mkdir(exist_ok=True)

    report = validate(project_dir)
    if not report.valid:
        print("Session not started — schema invalid:")
        report.print_report()
        return {}

    schema = report.schema
    now = datetime.now(timezone.utc).isoformat()


    # ── TRE portal redirect (planned) ──────────────────────────────────────
    # When this feature is fully implemented, crio.source() will detect
    # SCE tier 4+ and automatically open the TRE portal in the browser,
    # pre-populated with the project UUID. For now it warns and continues.
    if not sandbox and schema.compute.sce_tier.value >= 4:
        import webbrowser
        project_id = str(schema.project.id)
        portal_url = (
            f"https://tre.advocatehealth.org/projects/{project_id}"
            f"?source=crio&version={schema.phenotype.version}"
        )
        print("\n⚠  SCE tier 4+ detected.")
        print("   Full TRE portal integration is a planned feature.")
        print(f"   When live, your browser will open to: {portal_url}")
        print("   For now: open the TRE portal manually and source from within.\n")
    # ── end planned feature ─────────────────────────────────────────────────
    if sandbox:
        session = {**SANDBOX_CREDENTIALS}
        session["issued_at"] = now
        session["sce_tier"] = schema.compute.sce_tier.value
        session["environment"] = schema.compute.environment.value
        session["project_id"] = str(schema.project.id)
        session["pi_orcid"] = schema.investigator.pi_orcid
    else:
        raise NotImplementedError(
            "Production credential endpoint not yet configured. "
            "Run with sandbox=True for local development."
        )

    lock_path = project_dir / SESSION_LOCK
    with open(lock_path, "w") as f:
        json.dump(session, f, indent=2)

    os.environ["CRIO_PROJECT_ID"] = session["project_id"]
    os.environ["CRIO_SCE_TIER"] = str(session["sce_tier"])
    os.environ["CRIO_ENVIRONMENT"] = session["environment"]
    os.environ["CRIO_SANDBOX"] = "true" if sandbox else "false"
    os.environ["CRIO_PI_ORCID"] = session["pi_orcid"]

    print("✓ Session started")
    print(f"  Project:     {schema.phenotype.name}")
    print(f"  SCE tier:    {session['sce_tier']}")
    print(f"  Environment: {session['environment']}")
    print(f"  Mode:        {session['mode']}")

    return session
