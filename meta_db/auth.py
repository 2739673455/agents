from datetime import datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from pwdlib._hash import PasswordHash
from util import auth_logger

SECRET_KEY = "d6a5d730ec247d487f17419df966aec9d4c2a09d2efc9699d09757cf94c68b01"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

ALL_SCOPES = {
    "save_metadata": "写入元数据",
    "clear_metadata": "清空元数据",
    "get_table": "获取表信息",
    "get_column": "获取字段信息",
    "retrieve_knowledge": "检索知识",
    "retrieve_column": "检索字段",
    "retrieve_cell": "检索单元格",
}

GROUP_DB = {
    "root": {"allowed_scopes": list(ALL_SCOPES.keys())},
    "guest": {"allowed_scopes": []},
    "atguigu": {
        "allowed_scopes": [
            "get_table",
            "get_column",
            "retrieve_knowledge",
            "retrieve_column",
            "retrieve_cell",
        ]
    },
}

USER_DB = {
    "root": {
        "group": "root",
        "username": "root",
        "email": "root@example.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$fMuhnWBkGYj3r25EZnf6OA$4MRww1o4TWdfmmrYIu6H90+uQ6pMD+V6wd4B1UYnMp0",  # 123321
        "yn": 1,
    },
    "atguigu": {
        "group": "atguigu",
        "username": "atguigu",
        "email": "atguigu@example.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$fMuhnWBkGYj3r25EZnf6OA$4MRww1o4TWdfmmrYIu6H90+uQ6pMD+V6wd4B1UYnMp0",  # 123321
        "yn": 1,
    },
    "zhangsan": {
        "group": "guest",
        "username": "zhangsan",
        "email": "zhangsan@example.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$fMuhnWBkGYj3r25EZnf6OA$4MRww1o4TWdfmmrYIu6H90+uQ6pMD+V6wd4B1UYnMp0",  # 123321
        "yn": 1,
    },
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token", scopes=ALL_SCOPES)
password_hash = PasswordHash.recommended()


async def create_access_token(
    username: str,
    password: str,
    scopes: list[str],
    client_ip: str,
):
    # 验证用户名、密码
    auth_logger.info(f"{client_ip} | {username} | {scopes}: request token")
    user = USER_DB.get(username)
    target_hash = (
        user["hashed_password"] if user else password_hash.hash("dummy_password")
    )  # 如果用户不存在，使用 dummy_password 进行验证，避免时间攻击
    password_correct = password_hash.verify(password, target_hash)
    if not (user and password_correct):
        auth_logger.info(f"{client_ip} | {username} | {scopes}: validation user failed")
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    # 验证权限范围
    if exceed_scopes := set(scopes) - set(GROUP_DB[user["group"]]["allowed_scopes"]):
        auth_logger.info(
            f"{client_ip} | {username} | {scopes}: validation scope failed"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Requested scopes {exceed_scopes} exceed user's permissions",
        )

    # 创建访问令牌
    payload = {"sub": username, "group": user["group"], "scope": " ".join(scopes)}
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**payload, "exp": expire}
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    auth_logger.info(f"{client_ip} | {username} | {scopes}: create token success")

    return {"access_token": access_token, "token_type": "bearer"}


async def authentication(
    security_scopes: SecurityScopes, token: Annotated[str, Depends(oauth2_scheme)]
):
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
    if not ((username := payload.get("sub")) and (user := USER_DB.get(username))):
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
