from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
import re

from pydantic import BaseModel, field_validator, model_validator, Field


class SCETier(int, Enum):
    one   = 1
    two   = 2
    three = 3
    four  = 4
    five  = 5


class DataTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Environment(str, Enum):
    azure_tre = "azure_tre"
    gcp       = "gcp"
    local     = "local"


class IRBStatus(str, Enum):
    active  = "active"
    exempt  = "exempt"
    pending = "pending"


class ContributorRole(str, Enum):
    researcher        = "researcher"
    clinical_ops      = "clinical_ops"
    data_scientist    = "data_scientist"
    quality_analyst   = "quality_analyst"
    informaticist     = "informaticist"


class PhenotypeDomain(str, Enum):
    condition   = "condition"
    drug        = "drug"
    procedure   = "procedure"
    measurement = "measurement"
    observation = "observation"


class ValidationStatus(str, Enum):
    draft              = "draft"
    internal_validated = "internal_validated"
    peer_reviewed      = "peer_reviewed"
    deprecated         = "deprecated"


class ValidationMethod(str, Enum):
    cohort_diagnostics = "cohort_diagnostics"
    phevaluator        = "phevaluator"
    chart_review       = "chart_review"
    none               = "none"


class Contributor(BaseModel):
    name:    str
    orcid:   Optional[str] = None
    staff_id: Optional[str] = None
    role:    Optional[ContributorRole] = None

    @field_validator("orcid")
    @classmethod
    def validate_orcid(cls, v):
        if v and not re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", v):
            raise ValueError("ORCID must match format 0000-0000-0000-0000")
        return v

    @model_validator(mode="after")
    def requires_one_identifier(self):
        if not self.orcid and not self.staff_id:
            raise ValueError(
                "Contributor must have either orcid or staff_id"
            )
        return self


class ProjectBlock(BaseModel):
    id:                   UUID
    created:              datetime
    updated:              datetime
    derived_from:         Optional[str] = None
    derived_version:      Optional[str] = None
    derivation_rationale: Optional[str] = None


class InvestigatorBlock(BaseModel):
    pi_name:   str
    pi_email:  str
    pi_role:   ContributorRole = ContributorRole.researcher
    pi_orcid:  Optional[str]   = None
    staff_id:  Optional[str]   = None
    contributors: list[Contributor] = Field(default_factory=list)

    @field_validator("pi_orcid")
    @classmethod
    def validate_orcid(cls, v):
        if v and not re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", v):
            raise ValueError("ORCID must match format 0000-0000-0000-0000")
        return v

    @field_validator("pi_email")
    @classmethod
    def institutional_email(cls, v):
        allowed = {"wakehealth.edu", "wfusm.edu", "advocatehealth.com", "advocatehealth.org"}
        domain = v.split("@")[-1].lower() if "@" in v else ""
        if domain not in allowed:
            raise ValueError(
                f"Email must be an institutional address: {sorted(allowed)}"
            )
        return v

    @model_validator(mode="after")
    def requires_one_identifier(self):
        if not self.pi_orcid and not self.staff_id:
            raise ValueError(
                "Investigator must have either pi_orcid or staff_id"
            )
        return self

    @property
    def primary_identifier(self) -> str:
        return self.pi_orcid or self.staff_id


class InstitutionBlock(BaseModel):
    department:     str
    irb_number:     Optional[str]       = None
    irb_status:     Optional[IRBStatus] = None
    funding_source: Optional[str]       = None


class ComputeBlock(BaseModel):
    sce_tier:     SCETier
    data_tier:    DataTier
    environment:  Environment
    requested_at: datetime
    approved_at:  Optional[datetime] = None
    expires_at:   Optional[datetime] = None


class PhenotypeBlock(BaseModel):
    name:               str
    version:            str
    domain:             PhenotypeDomain
    omop_aligned:       bool
    clarity_required:   bool
    target_concept_ids: list[int] = Field(default_factory=list)
    icd_codes:          list[str] = Field(default_factory=list)
    description:        str
    inclusion_criteria: str
    exclusion_criteria: str
    validation_status:  ValidationStatus
    validation_method:  ValidationMethod
    ppv:                Optional[float] = Field(None, ge=0.0, le=1.0)
    phekb_id:           Optional[str]   = None
    ohdsi_pl_id:        Optional[str]   = None
    inherited_criteria: Optional[list]  = None

    @model_validator(mode="after")
    def check_conditional_fields(self):
        if self.omop_aligned and not self.target_concept_ids:
            raise ValueError(
                "target_concept_ids required when omop_aligned is true"
            )
        if self.validation_method == ValidationMethod.chart_review \
                and self.ppv is None:
            raise ValueError(
                "ppv required when validation_method is chart_review"
            )
        return self

    @field_validator("version")
    @classmethod
    def semver(cls, v):
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError("version must be semantic: MAJOR.MINOR.PATCH")
        return v


class ContributionBlock(BaseModel):
    deposit_eligible:  Optional[bool]     = None
    deposit_submitted: Optional[bool]     = None
    deposit_date:      Optional[datetime] = None
    credit_granted:    Optional[bool]     = None


class OutputsBlock(BaseModel):
    reusable_assets:     list[str] = Field(default_factory=list)
    publications:        list[str] = Field(default_factory=list)
    downstream_projects: list[str] = Field(default_factory=list)


class CRIOSchema(BaseModel):
    project:      ProjectBlock
    investigator: InvestigatorBlock
    institution:  InstitutionBlock
    compute:      ComputeBlock
    phenotype:    PhenotypeBlock
    outputs:      OutputsBlock      = Field(default_factory=OutputsBlock)
    contribution: ContributionBlock = Field(default_factory=ContributionBlock)

    @model_validator(mode="after")
    def irb_required_for_sce_three_plus(self):
        if self.compute.sce_tier >= SCETier.three:
            if not self.institution.irb_number \
                    or not self.institution.irb_status:
                raise ValueError(
                    "irb_number and irb_status required for SCE tier 3+"
                )
        return self

    @model_validator(mode="after")
    def compute_deposit_eligibility(self):
        eligible = (
            self.phenotype.validation_status in (
                ValidationStatus.internal_validated,
                ValidationStatus.peer_reviewed,
            )
            and bool(self.investigator.primary_identifier)
            and bool(self.phenotype.description)
            and bool(self.phenotype.inclusion_criteria)
            and bool(self.phenotype.exclusion_criteria)
        )
        self.contribution.deposit_eligible = eligible
        return self
