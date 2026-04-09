from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

_SESSION_SALT = "session-cookie"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_session_cookie(user_id: str) -> str:
    return serializer.dumps(user_id, salt=_SESSION_SALT)


def verify_session_cookie(cookie_value: str) -> str | None:
    try:
        user_id: str = serializer.loads(
            cookie_value,
            salt=_SESSION_SALT,
            max_age=settings.SESSION_MAX_AGE,
        )
        return user_id
    except (SignatureExpired, BadSignature):
        return None