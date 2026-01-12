import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from config import CFG
from db_session import get_asession, get_session
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from pwdlib._hash import PasswordHash
from sqlalchemy import text
from util import auth_logger

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# 北京时间时区（UTC+8）
BEIJING_TZ = timezone(timedelta(hours=8))


def init_all_scopes():
    """从数据库加载所有权限范围"""
    all_scopes: dict[str, str] = {}
    with get_session(CFG.auth_db) as session:
        result = session.execute(text("SELECT name, description FROM scope"))
        rows = result.mappings().fetchall()
        for row in rows:
            all_scopes[row["name"]] = row["description"]
    return all_scopes


ALL_SCOPES = init_all_scopes()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", scopes=ALL_SCOPES)
password_hash = PasswordHash.recommended()
HASHED_DUMMY_PASSWORD = password_hash.hash("dummy_password")


def _create_refresh_token(username: str, scopes: list[str]):
    """创建刷新令牌"""
    jti = str(uuid.uuid4())  # JWT ID
    refresh_expire = datetime.now(BEIJING_TZ) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )
    refresh_payload = {
        "sub": username,
        "scope": " ".join(scopes),
        "exp": refresh_expire,
        "jti": jti,
    }
    refresh_token = jwt.encode(
        refresh_payload, CFG.auth.secret_key, algorithm=CFG.auth.algorithm
    )
    return {
        "jti": jti,
        "refresh_expire": refresh_expire,
        "refresh_token": refresh_token,
    }


def _create_access_token(jti: str, username: str, scopes: list[str]):
    """创建访问令牌"""
    access_expire = datetime.now(BEIJING_TZ) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_payload = {
        "sub": username,
        "scope": " ".join(scopes),
        "exp": access_expire,
        "jti": jti,
    }
    access_token = jwt.encode(
        access_payload, CFG.auth.secret_key, algorithm=CFG.auth.algorithm
    )
    return access_token


async def _store_refresh_token(jti: str, username: str, expires_at: datetime):
    """存储刷新令牌到数据库"""
    async with get_asession(CFG.auth_db) as session:
        await session.execute(
            text(
                "INSERT INTO refresh_token (jti, username, expires_at) "
                "VALUES (:jti, :username, :expires_at)"
            ),
            {"jti": jti, "username": username, "expires_at": expires_at},
        )
        await session.commit()


async def _revoke_refresh_token_in_db(jti: str, username: str) -> bool:
    """在数据库中撤销刷新令牌，返回是否成功"""
    async with get_asession(CFG.auth_db) as session:
        result = await session.execute(
            text(
                "UPDATE refresh_token SET yn = 0 "
                "WHERE jti = :jti AND username = :username AND yn = 1"
            ),
            {"jti": jti, "username": username},
        )
        await session.commit()
        return result.rowcount > 0  # type: ignore


async def _validate_refresh_token_in_db(jti: str, username: str):
    """在数据库中验证刷新令牌"""
    async with get_asession(CFG.auth_db) as session:
        result = await session.execute(
            text(
                "SELECT yn, expires_at FROM refresh_token "
                "WHERE jti = :jti AND username = :username"
            ),
            {"jti": jti, "username": username},
        )
        token_record = result.mappings().fetchone()

    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if not token_record["yn"]:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    expires_at = token_record["expires_at"]
    # 将数据库中的 naive datetime 转换为 aware datetime
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=BEIJING_TZ)
    if expires_at < datetime.now(BEIJING_TZ):
        raise HTTPException(status_code=401, detail="Refresh token has expired")


async def _authenticate_user(username: str, password: str, client_ip: str) -> dict:
    """验证用户名和密码，返回用户信息"""
    # 查询用户信息
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

    # 验证密码（使用 dummy_password 避免时间攻击）
    target_hash = user["hashed_password"] if user else HASHED_DUMMY_PASSWORD
    password_correct = password_hash.verify(password, target_hash)
    if not (password_correct and user):
        auth_logger.info(f"{client_ip} | {username}: validation user failed")
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user["yn"]:
        raise HTTPException(status_code=403, detail="Inactive user")

    # 返回用户信息
    scopes = user["scopes"].split(",") if user["scopes"] else []
    return {
        "name": user["name"],
        "group_name": user["group_name"],
        "email": user["email"],
        "yn": user["yn"],
        "scopes": scopes,
    }


async def create_refresh_token(username: str, password: str, client_ip: str):
    """创建刷新令牌和访问令牌"""
    # 验证用户名、密码
    user = await _authenticate_user(username, password, client_ip)
    allowed_scopes = user["scopes"]

    # 创建刷新令牌
    _result = _create_refresh_token(username, allowed_scopes)
    jti = _result["jti"]
    refresh_expire = _result["refresh_expire"]
    refresh_token = _result["refresh_token"]
    # 存储刷新令牌到数据库
    await _store_refresh_token(jti, username, refresh_expire)

    # 创建访问令牌
    access_token = _create_access_token(jti, username, allowed_scopes)

    auth_logger.info(f"{client_ip} | {username}: create tokens success")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def create_access_token(refresh_token: str, scopes: list[str], client_ip: str):
    """创建访问令牌"""
    # 解码刷新令牌
    try:
        payload = jwt.decode(
            refresh_token, CFG.auth.secret_key, algorithms=[CFG.auth.algorithm]
        )
    except (jwt.ExpiredSignatureError, jwt.exceptions.InvalidTokenError):
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    if (not (username := payload.get("sub"))) or (not (jti := payload.get("jti"))):
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    # 验证刷新令牌是否在数据库中且未被撤销
    await _validate_refresh_token_in_db(jti, username)

    # 验证权限范围
    refresh_token_scopes = payload.get("scope", "").split()
    # 如果没有选择权限，默认使用用户拥有的所有权限
    scopes = scopes if scopes else refresh_token_scopes
    if exceed_scopes := set(scopes) - set(refresh_token_scopes):
        # 请求的权限超出范围
        auth_logger.info(
            f"{client_ip} | {username} | {scopes}: validation scope failed"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Requested scopes {exceed_scopes} exceed user's permissions",
        )

    # 撤销旧的刷新令牌
    await _revoke_refresh_token_in_db(jti, username)
    # 生成新的刷新令牌
    _result = _create_refresh_token(username, refresh_token_scopes)
    jti = _result["jti"]
    refresh_expire = _result["refresh_expire"]
    refresh_token = _result["refresh_token"]
    # 存储新的刷新令牌到数据库
    await _store_refresh_token(jti, username, refresh_expire)

    # 创建访问令牌
    access_token = _create_access_token(jti, username, scopes)

    auth_logger.info(
        f"{client_ip} | {username} | {scopes}: refresh token success with rotation"
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def revoke_refresh_token(refresh_token: str, client_ip: str):
    """撤销刷新令牌"""
    # 解码刷新令牌
    try:
        payload = jwt.decode(
            refresh_token, CFG.auth.secret_key, algorithms=[CFG.auth.algorithm]
        )
    except (jwt.ExpiredSignatureError, jwt.exceptions.InvalidTokenError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if (not (username := payload.get("sub"))) or (not (jti := payload.get("jti"))):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # 更新数据库中的撤销标记
    success = await _revoke_refresh_token_in_db(jti, username)
    if not success:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    auth_logger.info(f"{client_ip} | {username}: revoke refresh token success")
    return {"message": "Logged out successfully"}


async def authentication(
    security_scopes: SecurityScopes,
    access_token: Annotated[str, Depends(oauth2_scheme)],
):
    authenticate_value = (
        f'Bearer scope="{security_scopes.scope_str}"'
        if security_scopes.scopes
        else "Bearer"
    )

    # 解码访问令牌
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

    # 验证访问令牌中是否存在字段
    if (not payload.get("sub")) or (not payload.get("exp")) or (not payload.get("jti")):
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
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
