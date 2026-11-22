from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_origins(origins: list[str]) -> list[str]:
    normalized = []

    for origin in origins:
        origin = origin.strip()

        if origin == "*":
            raise ValueError("Wildcard origins are not allowed")

        parsed = urlsplit(origin)

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                f"Invalid origin: {origin}. Provide an exact origin."
            )

        try:
            parsed.port
        except ValueError:
            raise ValueError(f"Invalid port in origin: {origin}")

        normalized.append(
            f"{parsed.scheme}://{parsed.netloc}".lower()
        )

    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate origins are not allowed")

    return normalized


class WidgetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    configuration: dict = Field(default_factory=dict)
    allowed_origins: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 2:
            raise ValueError("Widget name must contain at least 2 characters")

        return value

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, value: list[str]) -> list[str]:
        return validate_origins(value)


class WidgetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    configuration: dict | None = None
    allowed_origins: list[str] | None = Field(default=None, max_length=20)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if len(value) < 2:
            raise ValueError("Widget name must contain at least 2 characters")

        return value

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return None

        return validate_origins(value)


class WidgetResponse(BaseModel):
    id: str
    name: str
    public_id: str
    configuration: dict
    allowed_origins: list[str]
    version: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
