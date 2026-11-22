from starlette.types import ASGIApp, Scope, Receive, Send


class BodySizeLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        max_body_size: int = 65536,
    ):
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not scope["path"].endswith("/submissions")
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")

        if content_length:
            try:
                if int(content_length) > self.max_body_size:
                    await self.reject(send)
                    return
            except ValueError:
                await self.reject(send)
                return

        messages = []
        total_size = 0

        while True:
            message = await receive()

            if message["type"] == "http.disconnect":
                return

            total_size += len(message.get("body", b""))

            if total_size > self.max_body_size:
                await self.reject(send)
                return

            messages.append(message)

            if not message.get("more_body", False):
                break

        index = 0

        async def replay_receive():
            nonlocal index

            if index < len(messages):
                message = messages[index]
                index += 1
                return message

            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)

    async def reject(self, send: Send):
        body = b'{"detail":"Request body too large"}'

        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })

        await send({
            "type": "http.response.body",
            "body": body,
        })
