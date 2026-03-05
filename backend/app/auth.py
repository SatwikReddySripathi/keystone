"""
API key authentication and org scoping.

Every request sends X-API-Key header.
We hash it, look it up, return the org_id.
All subsequent queries are scoped to that org — this is the multi-tenancy.
"""
import hashlib
from fastapi import Header, HTTPException
from app.db import get_db


def authenticate(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """
    FastAPI dependency that validates the API key.
    Returns org_id if valid, raises 401 if not.

    Usage in routes:
        @router.get("/something")
        def my_route(org_id: str = Depends(authenticate)):
            # org_id is guaranteed valid here
    """
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    with get_db() as conn:
        row = conn.execute(
            "SELECT org_id FROM api_keys WHERE key_hash = ?",
            (key_hash,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return row["org_id"]