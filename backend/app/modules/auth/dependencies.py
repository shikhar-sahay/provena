"""Authentication dependencies and reusable RBAC helpers.

Auth approach: JWT bearer access tokens. The React client sends
``Authorization: Bearer <token>`` and stores the token in localStorage.
That tradeoff (XSS-readable storage) is acceptable for this local student
application and is documented in docs/architecture.md; a production
deployment should prefer httpOnly cookies. Logout discards the token
client-side and records a USER_LOGOUT audit event server-side.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.users.models import Role, User
from app.modules.users.service import get_by_id

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token."
        )
    user = get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    """Dependency factory enforcing role membership (403 otherwise)."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in {r.value for r in roles}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        return user

    return checker


require_admin = require_roles(Role.ADMIN)
