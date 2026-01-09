from datetime import datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes,
)
from pwdlib import PasswordHash

SECRET_KEY = "d6a5d730ec247d487f17419df966aec9d4c2a09d2efc9699d09757cf94c68b01"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

ALL_SCOPES = {
    "health": "服务健康检查",
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
    "atguigu": {
        "allowed_scopes": [
            "health",
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
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$fMuhnWBkGYj3r25EZnf6OA$4MRww1o4TWdfmmrYIu6H90+uQ6pMD+V6wd4B1UYnMp0",
        "yn": 1,
    },
    "atguigu": {
        "group": "root",
        "username": "root",
        "email": "root@example.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$fMuhnWBkGYj3r25EZnf6OA$4MRww1o4TWdfmmrYIu6H90+uQ6pMD+V6wd4B1UYnMp0",
        "yn": 1,
    },
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", scopes=ALL_SCOPES)
password_hash = PasswordHash.recommended()


async def get_current_user(
    security_scopes: SecurityScopes, token: Annotated[str, Depends(oauth2_scheme)]
):
    authenticate_value = (
        f'Bearer scope="{security_scopes.scope_str}"'
        if security_scopes.scopes
        else "Bearer"
    )
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    # 验证用户
    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
    user = USER_DB.get(username)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
    # 验证权限
    token_scopes = set(payload.get("scope", "").split(" "))
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=401,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return user


async def login_for_access_token(req: Annotated[OAuth2PasswordRequestForm, Depends()]):
    username = req.username
    password = req.password
    scopes = req.scopes

    # 验证用户名、密码
    user = USER_DB.get(username)
    if not (user and password_hash.verify(password, user["password"])):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    # 创建访问令牌
    payload = {"sub": username, "scope": " ".join(scopes)}
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**payload, "exp": expire}
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": access_token, "token_type": "bearer"}
