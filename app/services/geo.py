import ipaddress

import httpx


def lookup_with_primary(ip: str) -> dict | None:
    response = httpx.get(
        f"http://ip-api.com/json/{ip}",
        params={"fields": "status,country,city"},
        timeout=2.5,
    )
    response.raise_for_status()
    result = response.json()

    if result.get("status") != "success":
        return None

    return {
        "country": result.get("country"),
        "city": result.get("city"),
    }


def lookup_with_fallback(ip: str) -> dict | None:
    response = httpx.get(
        f"https://ipapi.co/{ip}/json/",
        timeout=2.5,
    )
    response.raise_for_status()
    result = response.json()

    if result.get("error"):
        return None

    return {
        "country": result.get("country_name"),
        "city": result.get("city"),
    }


def get_location(ip: str | None) -> dict | None:
    if not ip:
        return None

    try:
        address = ipaddress.ip_address(ip)

        if not address.is_global:
            return None

    except ValueError:
        return None

    for provider in (lookup_with_primary, lookup_with_fallback):
        try:
            location = provider(ip)

            if location and (location.get("country") or location.get("city")):
                return location

        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            continue

    return None
