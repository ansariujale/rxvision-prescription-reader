from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, Session
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.ratelimit import auth_bucket, limit_by_ip
from app.core.security import DUMMY_HASH, create_token, hash_password, verify_password
from app.models import Scan, User
from app.schemas import DeleteAccountIn, LoginIn, PasswordIn, ProfileIn, RegisterIn, UserOut
from app.services.storage import get_storage

router = APIRouter(prefix="/auth", tags=["auth"])

rate_limited = [Depends(limit_by_ip(auth_bucket))]


def _set_session(response: Response, user: User) -> None:
    s = get_settings()
    response.set_cookie(
        s.cookie_name,
        create_token(user.id),
        max_age=s.jwt_ttl_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=201, dependencies=rate_limited)
async def register(body: RegisterIn, response: Response, session: Session):
    email = body.email.lower()
    exists = await session.scalar(select(func.count()).select_from(User).where(User.email == email))
    if exists:
        raise ApiError(409, "An account with this email already exists")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:  # lost a race with a concurrent signup
        await session.rollback()
        raise ApiError(409, "An account with this email already exists")
    _set_session(response, user)
    return user


@router.post("/login", response_model=UserOut, dependencies=rate_limited)
async def login(body: LoginIn, response: Response, session: Session):
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    # Same work and same message whether the email exists or not.
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not ok:
        raise ApiError(401, "Email or password is incorrect")
    _set_session(response, user)
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(get_settings().cookie_name, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
async def update_profile(body: ProfileIn, user: CurrentUser, session: Session):
    name = body.name.strip()
    if not name:
        raise ApiError(422, "Name is required")
    user.name = name
    await session.commit()
    return user


@router.post("/password", status_code=204, dependencies=rate_limited)
async def change_password(body: PasswordIn, user: CurrentUser, session: Session):
    if not verify_password(body.current_password, user.password_hash):
        raise ApiError(403, "Your current password is incorrect", code="wrong_password")
    user.password_hash = hash_password(body.new_password)
    await session.commit()


@router.delete("/me", status_code=204, dependencies=rate_limited)
async def delete_account(body: DeleteAccountIn, response: Response, user: CurrentUser, session: Session):
    """Delete the account, every scan, item, dose log and stored image."""
    if not verify_password(body.password, user.password_hash):
        raise ApiError(403, "Your password is incorrect", code="wrong_password")
    keys = list((await session.execute(select(Scan.image_key).where(Scan.user_id == user.id))).scalars())
    await session.delete(user)
    await session.commit()
    storage = get_storage()
    for key in keys:
        storage.delete(key)
    response.delete_cookie(get_settings().cookie_name, path="/")
