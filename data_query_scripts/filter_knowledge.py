import asyncio
from typing import Callable

from config import CFG
from state_manage import read_callback, write_callback
from util import ask_llm, get_prompt, kn_info_xml_str, parse_json


async def filter_knowledge(
    r_callback: Callable | None = None,
    w_callback: Callable | None = None,
):
    """LLM筛选指标知识"""
    state = await r_callback() if r_callback else {}
    query = state["query"]
    kn_map = state["kn_map"]
    filter_model = CFG.llm.filter_model

    if not kn_map:
        print("knowledge is empty")
        return

    prompt = get_prompt(
        "table_rag",
        "knowledge_filter_prompt",
        knowledge_info=kn_info_xml_str(kn_map),
        query=query,
    )
    resp = await ask_llm(
        filter_model,
        [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ],
        1,
        20,
    )
    filtered_kn_codes = parse_json(resp)
    filtered_kn_codes = {kn_code for kn_code in filtered_kn_codes if kn_code in kn_map}
    add_kn_codes: set[int] = {
        rel_code
        for kn_code in filtered_kn_codes
        for rel_code in (kn_map[kn_code].rel_kn or [])
        if rel_code not in filtered_kn_codes
    }  # 补充可能在过滤中遗漏掉的关联知识
    kn_map = {k: kn_map[k] for k in filtered_kn_codes | add_kn_codes}

    if w_callback:
        await w_callback({"kn_map": kn_map})


if __name__ == "__main__":
    asyncio.run(filter_knowledge(read_callback, write_callback))
