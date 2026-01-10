from datetime import datetime, timedelta
from typing import Annotated

import jwt
from config import CFG
from db_session import get_asession, get_session
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from pwdlib._hash import PasswordHash
from sqlalchemy import text
from util import auth_logger

SECRET_KEY = "d6a5d730ec247d487f17419df966aec9d4c2a09d2efc9699d09757cf94c68b01"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def init_all_scopes():
    """从数据库加载所有权限范围"""
    all_scopes: dict[str, str] = {}
    with get_session(CFG.auth_db) as session:
        result = session.execute(text("SELECT name, description FROM scope"))
        rows = result.mappings().fetchall()
        for row in rows:
            all_scopes[row["name"]] = row["description"]
    auth_logger.info(f"all scopes loaded: {list(all_scopes.keys())}")
    return all_scopes


ALL_SCOPES = init_all_scopes()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token", scopes=ALL_SCOPES)
password_hash = PasswordHash.recommended()


async def create_access_token(
    username: str,
    password: str,
    scopes: list[str],
    client_ip: str,
):
    # 验证用户名、密码
    async with get_asession(CFG.auth_db) as session:
        result = await session.execute(
            text(
                "SELECT user.*, GROUP_CONCAT(scope.name) as scopes "
                "FROM user "
                "LEFT JOIN group_scope_rel ON user.group_name = group_scope_rel.group_name "
                "LEFT JOIN scope ON group_scope_rel.scope_name = scope.name "
                "WHERE user.name = :username "
                "GROUP BY user.name"
            ),
            {"username": username},
        )
        user = result.mappings().fetchone()
    target_hash = (
        user["hashed_password"] if user else password_hash.hash("dummy_password")
    )  # 如果用户不存在，使用 dummy_password 进行验证，避免时间攻击
    password_correct = password_hash.verify(password, target_hash)
    if not (user and password_correct):
        auth_logger.info(f"{client_ip} | {username} | {scopes}: validation user failed")
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    # 验证权限范围
    allowed_scopes = user["scopes"].split(",") if user["scopes"] else []
    if exceed_scopes := set(scopes) - set(allowed_scopes):
        auth_logger.info(
            f"{client_ip} | {username} | {scopes}: validation scope failed"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Requested scopes {exceed_scopes} exceed user's permissions",
        )

    # 如果没有选择权限，默认返回用户拥有的所有权限
    scopes = scopes if scopes else allowed_scopes
    # 创建访问令牌
    payload = {"sub": username, "scope": " ".join(scopes)}
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**payload, "exp": expire}
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    auth_logger.info(f"{client_ip} | {username} | {scopes}: create token success")

    return {"access_token": access_token, "token_type": "bearer"}


async def authentication(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
):
    # 检查 scopes 是否已初始化
    authenticate_value = (
        f'Bearer scope="{security_scopes.scope_str}"'
        if security_scopes.scopes
        else "Bearer"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.exceptions.InvalidTokenError):
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )

    # 验证用户
    if not (username := payload.get("sub")):
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
    async with get_asession(CFG.auth_db) as session:
        result = await session.execute(
            text("SELECT user.yn FROM user WHERE user.name = :username"),
            {"username": username},
        )
        user = result.mappings().fetchone()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
    if not user["yn"]:
        raise HTTPException(
            status_code=401,
            detail="Inactive user",
            headers={"WWW-Authenticate": authenticate_value},
        )

    # 验证权限范围
    token_scopes = set(payload.get("scope", "").split())
    if set(security_scopes.scopes) - token_scopes:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": authenticate_value},
        )
