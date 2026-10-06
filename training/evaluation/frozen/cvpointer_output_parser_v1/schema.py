"""Shared CV/JD parsing contract from the team's resume-parsing design document.

Version 2.0. Missing text is "", missing collections are [], and missing numbers
are null. Every key is required. Name, email, and phone are always [MASKED].
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


SCHEMA_VERSION = "2.0"
MASKED = "[MASKED]"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PersonalInfo(StrictModel):
    name: str = Field(description="Always [MASKED]", json_schema_extra={"enum": [MASKED]})
    email: str = Field(description="Always [MASKED]", json_schema_extra={"enum": [MASKED]})
    phone: str = Field(description="Always [MASKED]", json_schema_extra={"enum": [MASKED]})
    github_url: str

    @field_validator("name", "email", "phone")
    @classmethod
    def require_mask(cls, value: str) -> str:
        if value != MASKED:
            raise ValueError("PII fields must be [MASKED]")
        return value


class CVSkills(StrictModel):
    hard_skills: list[str]
    soft_skills: list[str]


class CVExperience(StrictModel):
    company: str
    job_title: str
    duration: str
    description: str


class CVProject(StrictModel):
    name: str
    role: str
    technologies: list[str]
    details: str


class CVEducation(StrictModel):
    degree: str
    university: str
    gpa: float | None
    year_graduated: int | None


class CVSchema(StrictModel):
    personal_info: PersonalInfo
    summary: str
    skills: CVSkills
    experience: list[CVExperience]
    projects: list[CVProject]
    education: list[CVEducation]
    certifications: list[str]
    activities: list[str]
    awards: list[str]


class JDRequirements(StrictModel):
    must_have: list[str]
    nice_to_have: list[str]
    min_experience_years: float | None
    education: str


class JDSchema(StrictModel):
    job_title: str
    requirements: JDRequirements
    responsibilities: list[str]
    seniority_level: str
