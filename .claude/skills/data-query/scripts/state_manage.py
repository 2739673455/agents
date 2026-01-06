import json
from pathlib import Path

from filelock import FileLock

SESSION_DIR = Path(__file__).parent.parent / "session"
STATE_FILE = SESSION_DIR / "state.json"
LOCK_FILE = SESSION_DIR / "state.json.lock"
LOCK_TIMEOUT = 5


async def write_state_to_json(data: dict):
    """保存状态到JSON文件"""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
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


async def read_state_from_json():
    """从JSON文件读取状态"""
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
