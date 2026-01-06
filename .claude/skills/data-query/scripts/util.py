import asyncio
import functools
import json
import re
from pathlib import Path
from typing import Any, Callable, Coroutine, ParamSpec, Tuple, Type, TypeVar

import yaml
from config import CFG
from jinja2 import Template
from openai import AsyncOpenAI

P = ParamSpec("P")
R = TypeVar("R")


def async_retry(
    max_retries: int,
    timeout: float | None,
    backoff_factor: float = 1.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    异步重试装饰器

    Args:
        max_retries: 最大重试次数（默认值，可被 kwargs 中的 max_retries 覆盖）
        timeout: 单次请求超时时间（秒），None 表示不设置超时（默认值，可被 kwargs 中的 timeout 覆盖）
        backoff_factor: 退避因子，每次重试等待时间 = backoff_factor * (2 ** retry_count)
        retryable_exceptions: 可重试的异常类型
    """

    def decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 中提取超时和重试参数，优先使用传入值
            actual_timeout = kwargs.pop("timeout", timeout)
            actual_max_retries = kwargs.pop("max_retries", max_retries)
            last_exception = None

            for attempt in range(actual_max_retries + 1):
                try:
                    if actual_timeout is None:
                        return await func(*args, **kwargs)
                    return await asyncio.wait_for(
                        func(*args, **kwargs), timeout=actual_timeout
                    )
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < actual_max_retries:
                        wait_time = backoff_factor * (2**attempt)
                        await asyncio.sleep(wait_time)
                        continue
                    raise
                except asyncio.TimeoutError:
                    if attempt < actual_max_retries:
                        wait_time = backoff_factor * (2**attempt)
                        await asyncio.sleep(wait_time)
                        continue
                    raise TimeoutError(
                        f"Request timed out after {actual_timeout}s (retries: {actual_max_retries})"
                    )

            raise (
                last_exception
                if last_exception
                else RuntimeError("Max retries exceeded")
            )

        return wrapper

    return decorator


@async_retry(max_retries=1, timeout=None)
async def ask_llm(
    name: str,
    messages,
    max_retries: int = 0,
    timeout: float | None = None,
) -> str:
    """请求 LLM"""
    # 从配置中获取指定模型的配置信息
    model_config = CFG.llm.models[name]
    # 创建异步 OpenAI 客户端
    client = AsyncOpenAI(
        base_url=model_config.base_url,  # API 基础URL
        api_key=model_config.api_key,  # API 密钥
    )
    # 调用 OpenAI Chat Completions API
    completion = await client.chat.completions.create(
        model=model_config.model,  # 指定使用的模型
        messages=messages,  # 对话消息列表
        **model_config.params,  # 其他模型参数(如温度、最大token等)
    )
    return completion.choices[0].message.content


def get_prompt(prompt_file: str, prompt_name: str, **kwargs):
    """构建提示词"""
    PROMPT_DIR = Path(__file__).parent / "prompts"
    prompt_data = yaml.safe_load(
        PROMPT_DIR.joinpath(f"{prompt_file}.yml").read_text(encoding="utf-8")
    )[prompt_name]

    # 验证必需的模板变量是否都已提供
    required_vars = prompt_data["required_vars"]
    missing_vars = [var for var in required_vars if var not in kwargs]
    if missing_vars:
        error_msg = f"missing prompt variables: {missing_vars}"
        raise ValueError(error_msg)

    # 使用 Jinja2 模板引擎渲染系统提示词和用户提示词
    system_prompt = Template(prompt_data["system_template"]).render(**kwargs)
    user_prompt = Template(prompt_data["user_template"]).render(**kwargs)

    return {"system": system_prompt, "user": user_prompt}


def parse_json(input_str):
    """解析 JSON 字符串，支持纯 JSON 格式和 Markdown 代码块格式"""
    try:
        # 首先尝试直接解析纯 JSON 字符串（去除首尾空白）
        return json.loads(input_str.strip())
    except Exception:
        # 如果直接解析失败，尝试从 Markdown 代码块中提取 JSON
        # 使用正则表达式匹配 ```json ... ``` 格式的代码块
        pattern = r"```json\s*([\s\S]*?)\s*```"
        match = re.findall(pattern, input_str)[0]
        # 解析提取出的 JSON 内容
        return json.loads(match)


def _tag(tag: str, val, is_json: bool = False):
    if (
        (not isinstance(val, (bool, int, float)))
        and (not val)
        and (isinstance(val, str) and not val.strip())
    ):
        return ""
    content = json.dumps(val, ensure_ascii=False) if is_json else val
    return f"<{tag}>{content}</{tag}>"


def tb_col_xml_str(tb_map: dict[str, dict], col_map: dict[str, dict[str, dict]]):
    """
    构建XML格式的表字段信息字符串

    <tables>
        <table>
            <table_code></table_code>
            <table_name></table_name>
            <table_meaning></table_meaning>
            <columns>
                <column><column_name></column_name><column_comment></column_comment>...</column>
                <column><column_name></column_name><column_comment></column_comment>...</column>
            </columns>
        </table>
    </tables>
    """

    def build_col_xml_str(col_dict: dict[str, dict]):
        """构建XML格式的字段信息字符串"""
        return "".join(
            [
                """
            <column>"""
                f"{_tag('column_name', c['col_name'])}"
                f"{_tag('column_comment', c['col_comment'])}"
                f"{_tag('column_meaning', c['col_meaning'])}"
                f"{_tag('column_alias', c['col_alias'])}"
                f"{_tag('column_json_meaning', c['field_meaning'], True)}"
                f"{_tag('fewshot', c['fewshot'])}"
                f"{_tag('cells', c['cells'])}"
                "</column>"
                for c in col_dict.values()
            ]
        )

    tb_xml_str = "".join(
        [
            f"""
    <table>
        <table_code>{tb_code}</table_code>
        <table_name>{tb_map[tb_code]["tb_name"]}</table_name>
        <table_meaning>{tb_map[tb_code]["tb_meaning"]}</table_meaning>
        <columns>{build_col_xml_str(col_dict)}
        </columns>
    </table>"""
            for tb_code, col_dict in col_map.items()
        ]
    )
    tb_xml_str = f"<tables>{tb_xml_str}\n</tables>"
    return tb_xml_str


def kn_info_xml_str(kn_map: dict[int, dict]):
    """构建XML格式的指标知识信息字符串"""
    kn_xml_str = "".join(
        [
            f"""
    <knowledge>"""
            f"{_tag('kn_code', k['kn_code'])}"
            f"{_tag('kn_name', k['kn_name'])}"
            f"{_tag('kn_def', k['kn_def'])}"
            f"{_tag('kn_desc', k['kn_desc'])}"
            f"{_tag('rel_kn', k['rel_kn'])}"
            f"{_tag('kn_alias', k['kn_alias'])}"
            "</knowledge>"
            for k in kn_map.values()
        ]
    )
    kn_xml_str = f"<knowledges>{kn_xml_str}\n</knowledges>"
    return kn_xml_str


def sql_result_xml_str(result_list: list[list[dict[str, str]]]):
    """
    构建SQL语句与查询结果字符串

    <sql_results>
        <id></id>
        <sql_result>
            <query></query>
            <sql></sql>
            <result></result>

            <query></query>
            <sql></sql>
            <error></error>
        </sql_result>
    </sql_results>
    """
    xml_str_list: list[str] = []
    xml_str_list.append("<sql_results>")
    for idx, result in enumerate(result_list):
        xml_str_list.append(f"\t<id>{idx}</id>")
        xml_str_list.append("\t<sql_result>")
        xml_str_list.append(
            "\n\n".join(
                [
                    f"\t\t<query>{r['query']}</query>\n"
                    f"\t\t<sql>{r['sql']}</sql>\n"
                    f"\t\t{_tag('result' if 'result' in r else 'error', r.get('result') or r.get('error'))}"
                    for r in result
                ]
            )
        )
        xml_str_list.append("\t</sql_result>")
    xml_str_list.append("</sql_results>")
    return "\n".join(xml_str_list)
