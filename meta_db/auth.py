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

ACCESS_TOKEN_EXPIRE_MINUTES = 3
REFRESH_TOKEN_EXPIRE_DAYS = 7


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
HASHED_DUMMY_PASSWORD = password_hash.hash("dummy_password")


async def create_refresh_token(username: str, password: str, client_ip: str):
    """创建刷新令牌"""
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
    # 获取哈希的用户密码；如果用户不存在，使用 dummy_password 进行验证，避免时间攻击
    target_hash = user["hashed_password"] if user else HASHED_DUMMY_PASSWORD
    password_correct = password_hash.verify(password, target_hash)
    if not (password_correct and user):
        auth_logger.info(f"{client_ip} | {username}: validation user failed")
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user["yn"]:
        auth_logger.info(f"{client_ip} | {username}: inactive user")
        raise HTTPException(status_code=403, detail="Inactive user")
    allowed_scopes = user["scopes"].split(",") if user["scopes"] else []

    # 创建刷新令牌
    expire = datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": username, "scope": " ".join(allowed_scopes), "exp": expire}
    refresh_token = jwt.encode(
        payload, CFG.auth.secret_key, algorithm=CFG.auth.algorithm
    )
    auth_logger.info(f"{client_ip} | {username}: create refresh token success")

    return {"refresh_token": refresh_token, "token_type": "bearer"}


async def create_access_token(refresh_token: str, scopes: list[str], client_ip: str):
    """创建访问令牌"""
    # 解码刷新令牌
    try:
        payload = jwt.decode(
            refresh_token, CFG.auth.secret_key, algorithms=[CFG.auth.algorithm]
        )
    except (jwt.ExpiredSignatureError, jwt.exceptions.InvalidTokenError):
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    if not (username := payload.get("sub")):
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    # 验证权限范围
    refresh_token_scopes = payload.get("scope", "").split()
    # 如果没有选择权限，默认使用用户拥有的所有权限
    scopes = scopes if scopes else refresh_token_scopes
    if exceed_scopes := set(scopes) - set(refresh_token_scopes):
        auth_logger.info(
            f"{client_ip} | {username} | {scopes}: validation scope failed"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Requested scopes {exceed_scopes} exceed user's permissions",
        )

    # 创建访问令牌
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "scope": " ".join(scopes), "exp": expire}
    access_token = jwt.encode(
        payload, CFG.auth.secret_key, algorithm=CFG.auth.algorithm
    )
    auth_logger.info(f"{client_ip} | {username} | {scopes}: create token success")

    return {"access_token": access_token, "token_type": "bearer"}


async def authentication(
    security_scopes: SecurityScopes,
    access_token: Annotated[str, Depends(oauth2_scheme)],
):
    authenticate_value = (
        f'Bearer scope="{security_scopes.scope_str}"'
        if security_scopes.scopes
        else "Bearer"
    )
    try:
        payload = jwt.decode(
            access_token, CFG.auth.secret_key, algorithms=[CFG.auth.algorithm]
        )
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
    token_scopes = payload.get("scope", "").split()
    if set(security_scopes.scopes) - set(token_scopes):
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": authenticate_value},
        )
