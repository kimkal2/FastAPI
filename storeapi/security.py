import datetime
import logging

from typing import Optional, Annotated, Literal

from fastapi import Depends, HTTPException, status, Request, WebSocket
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from storeapi.database import database, user_table


class WebSocketOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(
        self, request: Optional[Request] = None, websocket: Optional[WebSocket] = None
    ) -> Optional[str]:
        # If it's a websocket connection, treat it as the request object to read headers
        connection = request or websocket
        return await super().__call__(connection)


# Use this instance for your dependencies instead
# oauth2_scheme = WebSocketOAuth2PasswordBearer(tokenUrl="token")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = "1234"
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def create_credential_exception(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


logger = logging.getLogger(__name__)


def access_token_expire_minutes() -> int:
    return 30


def confirm_token_expire_minutes() -> int:
    return 1440


def create_access_token(email: str):
    logger.debug("Creating access token", extra={"email": email})
    print(f" expire {access_token_expire_minutes()}")

    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=access_token_expire_minutes()
    )
    jwt_data = {"sub": email, "exp": expire, "type": "access"}
    encoded_jwt = jwt.encode(jwt_data, key=SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_confirmation_token(email: str):
    logger.debug("Creating confirmation token", extra={"email": email})
    print(f" expire {confirm_token_expire_minutes()}")

    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=confirm_token_expire_minutes()
    )
    jwt_data = {"sub": email, "exp": expire, "type": "confirmation"}
    encoded_jwt = jwt.encode(jwt_data, key=SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_subject_for_token_type(
    token: str, type: Literal["access", "confirmation"]
) -> str:
    try:
        payload = jwt.decode(token, key=SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError as e:
        raise create_credential_exception("Token has expired") from e
    except JWTError as e:
        raise create_credential_exception("Invalid token") from e

    email = payload.get("sub")
    if email is None:
        raise create_credential_exception("Token is missing 'sub' field")

    token_type = payload.get("type")
    if token_type is None or token_type != type:
        raise create_credential_exception(
            f"Token has incorrect type, expected '{type}'"
        )

    return email


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


async def get_user(email: str):
    logger.info("Fetching user from the database", extra={"email": email})
    query = user_table.select().where(user_table.c.email == email)
    result = await database.fetch_one(query)
    if result:
        return result


async def authenticate_user(email: str, password: str):
    logger.debug("Authenticating user", extra={"email": email})
    user = await get_user(email)
    if not user:
        raise create_credential_exception("Invalid email or password")
    if not verify_password(password, user.password):
        raise create_credential_exception("Invalid email or password")
    if not user.confirmed:
        raise create_credential_exception("User has not confirmed email")

    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    logger.debug("Get current user")
    email = get_subject_for_token_type(token, "access")
    user = await get_user(email=email)
    if user is None:
        raise create_credential_exception("Could not find this user for this token")
    return user
