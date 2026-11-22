from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class SubmissionCreate(BaseModel):
    data: dict[StrictStr, StrictStr] = Field(min_length=1, max_length=30)

    model_config = ConfigDict(extra="forbid")

    @field_validator("data")
    @classmethod
    def validate_data(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned = {}

        for key, item in value.items():
            key = key.strip()

            if not key or len(key) > 80:
                raise ValueError("Field names must contain 1–80 characters")

            if len(item) > 5000:
                raise ValueError("Field values cannot exceed 5000 characters")

            if key in cleaned:
                raise ValueError("Duplicate field names are not allowed")

            cleaned[key] = item.strip()

        return cleaned


class SubmissionResponse(BaseModel):
    id: str
    widget_id: str
    data: dict[str, str]
    country: str | None = None
    city: str | None = None
    created_at: str
