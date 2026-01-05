import argparse
import asyncio
import json
from typing import Any


async def merge_col_cell(
    retrieved_col_map: dict[str, dict[str, dict[str, Any]]],
    retrieved_cell_map: dict[str, dict[str, dict[str, Any]]],
):
    """整合表字段字段值信息"""
    for tb_code, col in retrieved_cell_map.items():
        if tb_code not in retrieved_col_map:
            retrieved_col_map[tb_code] = {}
        for col_name, col_obj in col.items():
            if col_name not in retrieved_col_map[tb_code]:
                # col_map 中原本没有此列则添加
                retrieved_col_map[tb_code][col_name] = col_obj
            else:
                # col_map 中原本有此列则更新
                _col = retrieved_col_map[tb_code][col_name]
                if _col.get("cells") is None:
                    _col["cells"] = []
                _col["cells"] = list(set(_col["cells"] + col_obj["cells"]))
                _col["score"] = max(col_obj["score"], _col["score"])  # 取最高分
    return {"col_map": retrieved_col_map}


async def main():
    usage = "python merge_col_cell.py --retrieved_col_map 字段信息 --retrieved_cell_map 单元格信息"
    parser = argparse.ArgumentParser(description="合并字段与单元格信息", usage=usage)
    parser.add_argument("--retrieved_col_map", type=json.loads, help="字段信息")
    parser.add_argument("--retrieved_cell_map", type=json.loads, help="单元格信息")

    args = parser.parse_args()
    res = await merge_col_cell(args.retrieved_col_map, args.retrieved_cell_map)
    print(res)


if __name__ == "__main__":
    asyncio.run(main())
