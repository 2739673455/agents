import json
from pathlib import Path

from filelock import FileLock

SESSION_DIR = Path(__file__).parent.parent / "session"
LOCK_TIMEOUT = 5


async def write_state_to_json(data: dict, session_id: str = "default"):
    """保存状态到JSON文件"""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE = SESSION_DIR / session_id / "state.json"
    LOCK_FILE = SESSION_DIR / session_id / "state.json.lock"
    with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT):
        state = (
            {**json.loads(STATE_FILE.read_text(encoding="utf-8")), **data}
            if STATE_FILE.exists()
            else data
        )
        STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"{list(data.keys())} saved to: {STATE_FILE}")


async def read_state_from_json(session_id: str = "default"):
    """从JSON文件读取状态"""
    STATE_FILE = SESSION_DIR / session_id / "state.json"
    LOCK_FILE = SESSION_DIR / session_id / "state.json.lock"
    with FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT):
        state = (
            json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if STATE_FILE.exists()
            else {}
        )
    return state


async def write_callback(data: dict):
    await write_state_to_json(data)


async def read_callback():
    return await read_state_from_json()
