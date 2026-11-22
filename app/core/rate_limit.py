from fastapi import Request
from slowapi import Limiter


def rate_limit_key(request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    request_path = request.url.path
    public_id = request.path_params.get("public_id", "unknown")
    return f"{client_ip}:{request_path}:{public_id}"


limiter = Limiter(key_func=rate_limit_key)
