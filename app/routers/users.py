# app/routers/users.py

import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import asyncpg

from .auth import get_current_user, get_db

router = APIRouter(tags=["Users"])

logger = logging.getLogger(__name__)


# ────────────────────────────── SCHEMAS ──────────────────────────────

from pydantic import BaseModel


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    number_plate: Optional[str] = None


# ────────────────────────────── ENDPOINTS ──────────────────────────────


@router.get("/users/")
async def list_drivers(
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Return all users with role='driver', including their request count.
    Requires a valid JWT (any role may call this; restrict to admin role if needed).
    """
    rows = await db.fetch("""
        SELECT
            u.id,
            u.phone,
            u.full_name,
            u.number_plate,
            u.role,
            u.created_at,
            COALESCE(r.request_count, 0) AS request_count
        FROM users u
        LEFT JOIN (
            SELECT customer_phone, COUNT(*) AS request_count
            FROM service_requests
            GROUP BY customer_phone
        ) r ON r.customer_phone = u.phone
        WHERE u.role = 'driver'
        ORDER BY u.created_at DESC
    """)

    return [dict(row) for row in rows]


@router.patch("/users/me")
async def update_my_profile(
    body: UserProfileUpdate,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Update the authenticated driver's profile (full_name, number_plate).
    """
    updates = body.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_parts = []
    params = []
    for idx, (key, value) in enumerate(updates.items(), start=1):
        set_parts.append(f"{key} = ${idx}")
        params.append(value)

    params.append(user["id"])
    query = f"""
        UPDATE users
        SET {', '.join(set_parts)}
        WHERE id = ${len(params)}
        RETURNING id, phone, full_name, number_plate, role, created_at
    """

    row = await db.fetchrow(query, *params)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f"✅ [PATCH /users/me] Updated profile for user_id={user['id']}")
    return dict(row)
