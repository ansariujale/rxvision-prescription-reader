import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import decode_token
from app.db.session import get_session
from app.models import Scan, ScanItem, User

Session = Annotated[AsyncSession, Depends(get_session)]


def _token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(get_settings().cookie_name)


async def current_user(request: Request, session: Session) -> User:
    token = _token(request)
    user_id = decode_token(token) if token else None
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        raise ApiError(401, "Sign in to continue")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def load_owned_scan(session: AsyncSession, scan_id: uuid.UUID, user: User) -> Scan:
    """A scan the user owns, with items loaded. Someone else's scan is a 404."""
    scan = (
        await session.execute(
            select(Scan)
            .where(Scan.id == scan_id, Scan.user_id == user.id)
            .options(selectinload(Scan.items).joinedload(ScanItem.medicine))
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if scan is None:
        raise ApiError(404, "Scan not found")
    return scan


async def owned_scan(scan_id: uuid.UUID, session: Session, user: CurrentUser) -> Scan:
    return await load_owned_scan(session, scan_id, user)


OwnedScan = Annotated[Scan, Depends(owned_scan)]
