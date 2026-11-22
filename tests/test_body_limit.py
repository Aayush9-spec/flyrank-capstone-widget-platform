import pytest

from app.core.body_limit import BodySizeLimitMiddleware


@pytest.mark.asyncio
async def test_normal_request_passes_through():
    received = []

    async def app(scope, receive, send):
        message = await receive()
        received.append(message["body"])

    middleware = BodySizeLimitMiddleware(app, max_body_size=10)

    async def receive():
        return {
            "type": "http.request",
            "body": b"hello",
            "more_body": False,
        }

    async def send(message):
        pass

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/public/widgets/test/submissions",
        "headers": [(b"content-length", b"5")],
    }

    await middleware(scope, receive, send)
    assert received == [b"hello"]


@pytest.mark.asyncio
async def test_oversized_content_length_returns_413():
    responses = []

    async def app(scope, receive, send):
        raise AssertionError("Application should not be called")

    middleware = BodySizeLimitMiddleware(app, max_body_size=10)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        responses.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/public/widgets/test/submissions",
        "headers": [(b"content-length", b"11")],
    }

    await middleware(scope, receive, send)

    assert responses[0]["status"] == 413
    assert b"too large" in responses[1]["body"]


@pytest.mark.asyncio
async def test_streamed_oversized_body_returns_413():
    responses = []
    chunks = [
        {"type": "http.request", "body": b"123456", "more_body": True},
        {"type": "http.request", "body": b"78901", "more_body": False},
    ]

    async def app(scope, receive, send):
        raise AssertionError("Application should not be called")

    middleware = BodySizeLimitMiddleware(app, max_body_size=10)

    async def receive():
        return chunks.pop(0)

    async def send(message):
        responses.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/public/widgets/test/submissions",
        "headers": [],
    }

    await middleware(scope, receive, send)

    assert responses[0]["status"] == 413


@pytest.mark.asyncio
async def test_non_submission_request_bypasses_limit():
    called = []

    async def app(scope, receive, send):
        called.append(True)

    middleware = BodySizeLimitMiddleware(app, max_body_size=1)

    async def receive():
        return {"type": "http.request", "body": b"large", "more_body": False}

    async def send(message):
        pass

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/widgets",
        "headers": [],
    }

    await middleware(scope, receive, send)

    assert called == [True]


@pytest.mark.asyncio
async def test_invalid_content_length_returns_413():
    responses = []

    async def app(scope, receive, send):
        raise AssertionError("Application should not be called")

    middleware = BodySizeLimitMiddleware(app, max_body_size=10)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        responses.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/public/widgets/test/submissions",
        "headers": [(b"content-length", b"invalid")],
    }

    await middleware(scope, receive, send)

    assert responses[0]["status"] == 413