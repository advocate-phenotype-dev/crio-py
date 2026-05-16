from __future__ import annotations

import json
from pathlib import Path


def export(
    project_dir=None,
    target: str = "ohdsi_pl",
) -> dict:
    from crio.validate import validate

    project_dir = Path(project_dir or Path.cwd())

    report = validate(project_dir)
    if not report.valid:
        print("Export aborted — schema invalid:")
        report.print_report()
        return {}

    schema = report.schema

    if target == "ohdsi_pl":
        output = _to_ohdsi_pl(schema)
    elif target == "phekb":
        output = _to_phekb(schema)
    else:
        raise ValueError(f"Unknown export target: {target}. Use ohdsi_pl or phekb.")

    print(json.dumps(output, indent=2, default=str))
    return output


def _to_ohdsi_pl(schema) -> dict:
    contributors = [
        {"name": schema.investigator.pi_name, "orcid": schema.investigator.pi_orcid}
    ]
    for c in schema.investigator.contributors:
        contributors.append({"name": c.name, "orcid": c.orcid})

    return {
        "cohortDefinitionId": str(schema.project.id),
        "cohortDefinitionName": schema.phenotype.name,
        "cohortDefinitionDescription": schema.phenotype.description,
        "contributors": contributors,
        "clinicalDescription": schema.phenotype.description,
        "inclusionCriteria": schema.phenotype.inclusion_criteria,
        "exclusionCriteria": schema.phenotype.exclusion_criteria,
        "conceptDomain": schema.phenotype.domain.value,
        "omopConceptIds": schema.phenotype.target_concept_ids,
        "icdCodes": schema.phenotype.icd_codes,
        "validationStatus": schema.phenotype.validation_status.value,
        "validationMethod": schema.phenotype.validation_method.value,
        "ppv": schema.phenotype.ppv,
        "version": schema.phenotype.version,
        "sourceRegistry": "Advocate Health CRIO Phenotype Library",
        "sourceId": str(schema.project.id),
        "tags": [schema.phenotype.domain.value],
        "recommendedStudyApplications": [],
        "externalLinks": {
            "phekb": schema.phenotype.phekb_id,
            "ohdsi_pl": schema.phenotype.ohdsi_pl_id,
        },
        "createdDate": schema.project.created.isoformat(),
        "updatedDate": schema.project.updated.isoformat(),
    }


def _to_phekb(schema) -> dict:
    return {
        "title": schema.phenotype.name,
        "description": schema.phenotype.description,
        "inclusionCriteria": schema.phenotype.inclusion_criteria,
        "exclusionCriteria": schema.phenotype.exclusion_criteria,
        "dataModalities": ["EHR"],
        "icdCodes": schema.phenotype.icd_codes,
        "author": {
            "name": schema.investigator.pi_name,
            "orcid": schema.investigator.pi_orcid,
            "email": schema.investigator.pi_email,
        },
        "institution": schema.institution.department,
        "validationStatus": schema.phenotype.validation_status.value,
        "ppv": schema.phenotype.ppv,
        "version": schema.phenotype.version,
        "createdDate": schema.project.created.isoformat(),
    }
