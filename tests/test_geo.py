import httpx

from app.services import geo


def test_primary_provider_success(monkeypatch):
    monkeypatch.setattr(
        geo,
        "lookup_with_primary",
        lambda ip: {"country": "India", "city": "Kanpur"},
    )

    def unexpected_fallback(ip):
        raise AssertionError("Fallback should not be called")

    monkeypatch.setattr(geo, "lookup_with_fallback", unexpected_fallback)

    result = geo.get_location("8.8.8.8")

    assert result == {"country": "India", "city": "Kanpur"}


def test_primary_failure_uses_fallback(monkeypatch):
    monkeypatch.setattr(
        geo,
        "lookup_with_primary",
        lambda ip: (_ for _ in ()).throw(httpx.ConnectError("Primary unavailable")),
    )
    monkeypatch.setattr(
        geo,
        "lookup_with_fallback",
        lambda ip: {"country": "India", "city": "Kanpur"},
    )

    result = geo.get_location("8.8.8.8")

    assert result == {"country": "India", "city": "Kanpur"}


def test_both_providers_fail(monkeypatch):
    def fail(ip):
        raise httpx.ConnectError("Provider unavailable")

    monkeypatch.setattr(geo, "lookup_with_primary", fail)
    monkeypatch.setattr(geo, "lookup_with_fallback", fail)

    assert geo.get_location("8.8.8.8") is None


def test_private_ip_is_skipped(monkeypatch):
    def unexpected_provider(ip):
        raise AssertionError("Provider should not be called")

    monkeypatch.setattr(geo, "lookup_with_primary", unexpected_provider)
    monkeypatch.setattr(geo, "lookup_with_fallback", unexpected_provider)

    assert geo.get_location("192.168.1.10") is None
    assert geo.get_location("127.0.0.1") is None


def test_invalid_and_missing_ip(monkeypatch):
    def unexpected_provider(ip):
        raise AssertionError("Provider should not be called")

    monkeypatch.setattr(geo, "lookup_with_primary", unexpected_provider)
    monkeypatch.setattr(geo, "lookup_with_fallback", unexpected_provider)

    assert geo.get_location(None) is None
    assert geo.get_location("") is None
    assert geo.get_location("not-an-ip") is None


def test_primary_provider_empty_result_uses_fallback(monkeypatch):
    monkeypatch.setattr(geo, "lookup_with_primary", lambda ip: None)
    monkeypatch.setattr(
        geo,
        "lookup_with_fallback",
        lambda ip: {"country": "India", "city": "Delhi"},
    )

    assert geo.get_location("8.8.8.8") == {
        "country": "India",
        "city": "Delhi",
    }

from unittest.mock import Mock


def test_primary_provider_parses_success_response(monkeypatch):
    response = Mock()
    response.json.return_value = {
        "status": "success",
        "country": "India",
        "city": "Kanpur",
    }

    monkeypatch.setattr(
        geo.httpx,
        "get",
        lambda *args, **kwargs: response,
    )

    result = geo.lookup_with_primary("8.8.8.8")

    assert result == {"country": "India", "city": "Kanpur"}
    response.raise_for_status.assert_called_once()


def test_primary_provider_rejects_failed_status(monkeypatch):
    response = Mock()
    response.json.return_value = {"status": "fail"}

    monkeypatch.setattr(
        geo.httpx,
        "get",
        lambda *args, **kwargs: response,
    )

    assert geo.lookup_with_primary("8.8.8.8") is None


def test_fallback_provider_parses_success_response(monkeypatch):
    response = Mock()
    response.json.return_value = {
        "country_name": "India",
        "city": "Kanpur",
    }

    monkeypatch.setattr(
        geo.httpx,
        "get",
        lambda *args, **kwargs: response,
    )

    result = geo.lookup_with_fallback("8.8.8.8")

    assert result == {"country": "India", "city": "Kanpur"}
    response.raise_for_status.assert_called_once()


def test_fallback_provider_rejects_error_response(monkeypatch):
    response = Mock()
    response.json.return_value = {"error": True}

    monkeypatch.setattr(
        geo.httpx,
        "get",
        lambda *args, **kwargs: response,
    )

    assert geo.lookup_with_fallback("8.8.8.8") is None