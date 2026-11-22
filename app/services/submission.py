import re

from fastapi import HTTPException, status


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_submission(widget, data: dict[str, str]) -> dict[str, str]:
    configuration = widget.configuration or {}
    fields = configuration.get("fields", [])

    if not isinstance(fields, list) or not fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Widget has no configured fields",
        )

    allowed_fields = {
        field["name"]: field
        for field in fields
        if isinstance(field, dict) and isinstance(field.get("name"), str)
    }

    if not allowed_fields:
        raise HTTPException(status_code=422, detail="Invalid widget configuration")

    if "website" in data and data["website"].strip():
        raise HTTPException(status_code=422, detail="Submission rejected")

    unknown_fields = set(data) - set(allowed_fields)

    if unknown_fields:
        raise HTTPException(
            status_code=422,
            detail="Submission contains unknown fields",
        )

    cleaned = {}

    for name, field in allowed_fields.items():
        value = data.get(name, "").strip()

        if field.get("required") and not value:
            raise HTTPException(
                status_code=422,
                detail=f"{name} is required",
            )

        if len(value) > 5000:
            raise HTTPException(status_code=422, detail="Field value too long")

        if field.get("type") == "email" and value:
            if not EMAIL_PATTERN.match(value):
                raise HTTPException(status_code=422, detail="Invalid email address")

        cleaned[name] = value

    return cleaned
