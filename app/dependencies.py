import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.models import User
from app.database.session import get_db

# PHASE 1: Auth bypass — re-enable imports below before production
# from fastapi import HTTPException, status
# from fastapi.security import OAuth2PasswordBearer
# from app.core.security import decode_access_token
# from app.database.models import WorkspaceMember
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

PHASE1_BYPASS_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PHASE1_BYPASS_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
) -> User:
    # PHASE 1: Auth bypass — return a synthetic user without token validation
    return User(
        id=PHASE1_BYPASS_USER_ID,
        email="phase1-bypass@local",
        hashed_password="",
        is_active=True,
    )

    # --- Original auth logic (re-enable in phase 2) ---
    # token: Annotated[str, Depends(oauth2_scheme)],
    # try:
    #     payload = decode_access_token(token)
    #     user_id = payload.get("sub")
    #     if not user_id:
    #         raise ValueError("Missing subject")
    # except ValueError as exc:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Could not validate credentials",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     ) from exc
    #
    # user = db.get(User, uuid.UUID(user_id))
    # if not user or not user.is_active:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Inactive or missing user",
    #     )
    # return user


def verify_workspace_access(
    db: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> None:
    # PHASE 1: Auth bypass — skip workspace membership check
    return

    # --- Original auth logic (re-enable in phase 2) ---
    # membership = (
    #     db.query(WorkspaceMember)
    #     .filter(
    #         WorkspaceMember.user_id == user_id,
    #         WorkspaceMember.workspace_id == workspace_id,
    #     )
    #     .first()
    # )
    # if not membership:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="You do not have access to this workspace",
    #     )
