"""国内公开电商商品目录采集与标准化"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import threading
import time
import urllib.parse
import urllib.robotparser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from itertools import product as cartesian_product
from pathlib import Path
from typing import Any

import httpx
from scrapling.parser import Selector

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

CATALOG_DATASET_NAME = "国内公开电商商品页"
CATALOG_PRODUCT_SOURCE_SYSTEM = "PIM"
CATALOG_MERCHANT_SOURCE_SYSTEM = "MERCHANT_CENTER"
SUNING_DATASET_NAME = "苏宁易购公开商品页"
SUNING_DATASET_URL = "https://www.suning.com/"
SUNING_REPOSITORY_URL = "https://search.suning.com/"
SUNING_REVISION = "live"
SUNING_ORIGIN_PLATFORM = "SUNING"
SOURCE_CACHE = Path("source") / "suning_products.jsonl"
SOURCE_CACHE_METADATA = Path("source") / "suning_products.meta.json"
SOURCE_CRAWL_STATE = Path("source") / "suning_crawl_state.json"
SOURCE_VARIANT_STATE = Path("source") / "suning_variant_refresh_state.json"
PRICE_REGION_CODE = "025"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)
SEARCH_PAGE_LIMIT = 50
MAX_SOURCE_SKUS_PER_SPU = 40
CRAWL_WORKERS = 32
VARIANT_PARSER_REVISION = 2
VARIANT_REFRESH_CHECKPOINT = 512
SPU_DISCRIMINATOR_AXES = ("型号", "系列", "段位")


@dataclass(frozen=True, slots=True)
class DiscoveryQuery:
    group: str
    keyword: str


DISCOVERY_GROUP_WEIGHTS = {
    "家居家装": 19,
    "手机数码": 16,
    "服饰鞋包": 12,
    "母婴玩具": 11,
    "美妆个护": 8,
    "运动户外": 7,
    "食品饮料": 7,
    "电脑办公": 5,
    "汽车用品": 4,
    "宠物生活": 4,
    "家用电器": 4,
    "图书文娱": 0,
    "医药保健": 3,
}

DISCOVERY_KEYWORDS = {
    "家居家装": (
        "床上用品",
        "四件套",
        "被子",
        "枕头",
        "床垫",
        "床笠",
        "毛巾",
        "浴巾",
        "衣架",
        "晾衣架",
        "收纳用品",
        "收纳箱",
        "收纳柜",
        "置物架",
        "垃圾桶",
        "厨房用品",
        "保鲜盒",
        "炒锅",
        "汤锅",
        "煎锅",
        "菜刀",
        "砧板",
        "餐具",
        "水杯",
        "保温杯",
        "家具",
        "沙发",
        "床",
        "衣柜",
        "餐桌",
        "书桌",
        "电脑椅",
        "窗帘",
        "地毯",
        "灯具",
        "台灯",
        "吸顶灯",
        "吊灯",
        "智能门锁",
        "水龙头",
        "花洒",
        "浴室柜",
        "马桶",
        "五金工具",
        "电钻",
        "工具箱",
        "墙纸",
        "地板",
        "油漆",
        "开关插座",
    ),
    "手机数码": (
        "手机",
        "5G手机",
        "折叠屏手机",
        "游戏手机",
        "老人手机",
        "苹果手机",
        "华为手机",
        "小米手机",
        "荣耀手机",
        "OPPO手机",
        "vivo手机",
        "一加手机",
        "真我手机",
        "红魔手机",
        "手机壳",
        "手机膜",
        "手机充电器",
        "无线充电器",
        "充电宝",
        "手机数据线",
        "耳机",
        "蓝牙耳机",
        "头戴耳机",
        "运动耳机",
        "降噪耳机",
        "蓝牙音箱",
        "平板电脑",
        "电子书阅读器",
        "智能手表",
        "智能手环",
        "儿童电话手表",
        "数码相机",
        "微单相机",
        "运动相机",
        "摄像机",
        "无人机",
        "麦克风",
        "录音笔",
        "路由器",
        "网络摄像头",
        "行车运动相机",
    ),
    "服饰鞋包": (
        "女装",
        "男装",
        "连衣裙",
        "半身裙",
        "羽绒服",
        "冲锋衣",
        "夹克",
        "风衣",
        "衬衫",
        "卫衣",
        "针织衫",
        "T恤",
        "牛仔裤",
        "休闲裤",
        "运动裤",
        "内衣",
        "文胸",
        "睡衣",
        "袜子",
        "男鞋",
        "女鞋",
        "运动鞋",
        "跑鞋",
        "篮球鞋",
        "休闲鞋",
        "皮鞋",
        "凉鞋",
        "靴子",
        "拖鞋",
        "箱包",
        "双肩包",
        "单肩包",
        "手提包",
        "旅行箱",
        "钱包",
        "皮带",
        "帽子",
        "围巾",
        "手套",
        "太阳镜",
    ),
    "母婴玩具": (
        "奶粉",
        "婴儿奶粉",
        "羊奶粉",
        "纸尿裤",
        "拉拉裤",
        "婴儿湿巾",
        "奶瓶",
        "奶嘴",
        "吸奶器",
        "暖奶器",
        "婴儿推车",
        "儿童安全座椅",
        "婴儿床",
        "婴儿洗护",
        "宝宝辅食",
        "儿童餐具",
        "婴儿用品",
        "儿童玩具",
        "积木玩具",
        "毛绒玩具",
        "遥控玩具",
        "拼图玩具",
        "早教机",
        "点读笔",
        "儿童自行车",
        "儿童滑板车",
        "儿童书包",
        "儿童水杯",
        "儿童学习桌",
        "婴儿睡袋",
        "婴儿浴盆",
        "儿童牙刷",
        "儿童洗发水",
        "儿童机器人",
        "儿童乐器玩具",
    ),
    "美妆个护": (
        "护肤品",
        "洁面乳",
        "爽肤水",
        "精华液",
        "面霜",
        "眼霜",
        "面膜",
        "防晒霜",
        "卸妆水",
        "粉底液",
        "口红",
        "眼影",
        "眉笔",
        "香水",
        "洗发水",
        "护发素",
        "沐浴露",
        "身体乳",
        "牙膏",
        "牙刷",
        "电动牙刷",
        "剃须刀",
        "吹风机",
        "卷发棒",
        "美容仪",
        "卫生巾",
        "洗手液",
        "漱口水",
        "男士护肤",
        "染发剂",
    ),
    "运动户外": (
        "健身器材",
        "跑步机",
        "动感单车",
        "哑铃",
        "瑜伽垫",
        "筋膜枪",
        "跳绳",
        "篮球",
        "足球",
        "羽毛球拍",
        "乒乓球拍",
        "网球拍",
        "游泳镜",
        "泳衣",
        "户外装备",
        "帐篷",
        "睡袋",
        "登山杖",
        "户外背包",
        "户外水壶",
        "露营桌椅",
        "烧烤炉",
        "钓鱼竿",
        "自行车",
        "山地车",
        "轮滑鞋",
        "滑板",
        "运动护具",
        "望远镜",
        "户外手电筒",
    ),
    "食品饮料": (
        "牛奶",
        "酸奶",
        "奶粉食品",
        "饮用水",
        "矿泉水",
        "果汁",
        "碳酸饮料",
        "咖啡",
        "茶叶",
        "绿茶",
        "红茶",
        "白酒",
        "啤酒",
        "葡萄酒",
        "零食",
        "坚果",
        "饼干",
        "巧克力",
        "糖果",
        "肉干",
        "方便面",
        "速冻食品",
        "大米",
        "面粉",
        "食用油",
        "酱油",
        "食醋",
        "调味料",
        "蜂蜜",
        "麦片",
        "婴幼儿辅食",
        "水果罐头",
        "糕点",
        "月饼",
        "地方特产",
    ),
    "电脑办公": (
        "笔记本电脑",
        "台式电脑",
        "一体机电脑",
        "显示器",
        "电脑主机",
        "显卡",
        "主板",
        "电脑内存",
        "固态硬盘",
        "机械硬盘",
        "键盘",
        "鼠标",
        "电脑音箱",
        "电脑摄像头",
        "打印机",
        "复印机",
        "扫描仪",
        "投影仪",
        "碎纸机",
        "办公用品",
        "打印纸",
        "墨盒",
        "硒鼓",
        "计算器",
        "移动硬盘",
    ),
    "汽车用品": (
        "汽车用品",
        "行车记录仪",
        "车载充电器",
        "车载吸尘器",
        "车载冰箱",
        "汽车脚垫",
        "汽车坐垫",
        "汽车香水",
        "汽车贴膜",
        "雨刮器",
        "汽车轮胎",
        "机油",
        "汽车蓄电池",
        "洗车机",
        "汽车应急电源",
        "车载手机支架",
        "儿童安全座椅汽车",
        "汽车防冻液",
        "汽车玻璃水",
        "汽车遮阳挡",
    ),
    "宠物生活": (
        "宠物用品",
        "猫粮",
        "狗粮",
        "猫罐头",
        "狗罐头",
        "猫砂",
        "猫砂盆",
        "猫爬架",
        "猫抓板",
        "宠物窝",
        "宠物牵引绳",
        "宠物玩具",
        "宠物沐浴露",
        "宠物饮水机",
        "宠物自动喂食器",
        "宠物尿垫",
        "宠物零食",
        "水族箱",
        "鱼粮",
        "仓鼠用品",
    ),
    "家用电器": (
        "空调",
        "冰箱",
        "洗衣机",
        "电视机",
        "热水器",
        "油烟机",
        "燃气灶",
        "厨房电器",
        "电饭煲",
        "电压力锅",
        "微波炉",
        "电烤箱",
        "空气炸锅",
        "破壁机",
        "豆浆机",
        "榨汁机",
        "电水壶",
        "生活电器",
        "吸尘器",
        "扫地机器人",
        "空气净化器",
        "加湿器",
        "电风扇",
        "取暖器",
        "除湿机",
    ),
    "图书文娱": (),
    "医药保健": (
        "保健品",
        "维生素",
        "钙片",
        "鱼油",
        "蛋白粉",
        "益生菌",
        "膳食纤维",
        "阿胶",
        "燕窝",
        "人参",
        "枸杞",
        "医疗器械",
        "血压计",
        "血糖仪",
        "体温计",
        "制氧机",
        "雾化器",
        "按摩器",
        "护腰",
        "护膝",
    ),
}

DISCOVERY_QUERIES = tuple(
    DiscoveryQuery(group, keyword)
    for group, keywords in DISCOVERY_KEYWORDS.items()
    for keyword in keywords
)


@dataclass(frozen=True, slots=True)
class CatalogSku:
    source_key: str
    external_sku_id: str
    title: str
    specs: dict[str, str]
    sale_price_cny: str
    list_price_cny: str | None
    price_region_code: str | None
    image_url: str | None
    source_url: str


@dataclass(frozen=True, slots=True)
class CatalogProduct:
    source_key: str
    external_product_id: str
    origin_platform: str
    source_category: str
    source_category_ids: tuple[str, ...]
    title: str
    spu_name: str
    subtitle: str | None
    brand: str
    source_brand_id: str | None
    store: str
    source_store_id: str | None
    is_self_operated: bool
    is_cross_border: bool
    root_category: str
    second_category: str
    leaf_category: str
    source_category_path: tuple[str, ...]
    attributes: dict[str, str]
    model: str | None
    main_image_url: str | None
    source_weight: str | None
    source_volume: str | None
    weight_kg: str | None
    volume_m3: str | None
    review_count: int | None
    source_url: str
    captured_at: str
    selection_group: str
    skus: tuple[CatalogSku, ...]


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    vendor_code: str
    sku_code: str
    source_url: str

    @property
    def key(self) -> str:
        return f"{self.vendor_code}:{self.sku_code}"


class RateLimitedClient:
    def __init__(self, delay_seconds: float) -> None:
        if delay_seconds < 0:
            raise ValueError("采集间隔不能小于0")
        self.delay_seconds = delay_seconds
        self._lock = threading.Lock()
        self._source_lock = threading.Lock()
        self._claimed_source_keys: set[str] = set()
        self._next_request_at = 0.0
        self._client = httpx.Client(
            follow_redirects=True,
            headers={
                "Accept-Language": "zh-CN,zh;q=0.9",
                "User-Agent": USER_AGENT,
            },
            limits=httpx.Limits(
                max_connections=CRAWL_WORKERS,
                max_keepalive_connections=CRAWL_WORKERS,
                keepalive_expiry=30.0,
            ),
            timeout=12.0,
        )

    def get(self, url: str, *, referer: str | None = None) -> bytes:
        headers = {"Referer": referer} if referer else None
        last_error: Exception | None = None
        for attempt in range(3):
            with self._lock:
                wait_seconds = self._next_request_at - time.monotonic()
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
                self._next_request_at = time.monotonic() + self.delay_seconds
            try:
                response = self._client.get(url, headers=headers)
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as error:
                last_error = error
                time.sleep(min(8.0, 0.8 * 2**attempt))
        raise OSError(f"页面采集失败: {url}") from last_error

    def close(self) -> None:
        self._client.close()

    def claim_source(self, source_key: str) -> bool:
        with self._source_lock:
            if source_key in self._claimed_source_keys:
                return False
            self._claimed_source_keys.add(source_key)
            return True

    def claim_sources(self, source_keys: set[str]) -> None:
        with self._source_lock:
            self._claimed_source_keys.update(source_keys)

    def release_source(self, source_key: str) -> None:
        with self._source_lock:
            self._claimed_source_keys.discard(source_key)


def _clean_text(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _target_quotas(target_count: int) -> dict[str, int]:
    quotas = {
        group: target_count * weight // 100
        for group, weight in DISCOVERY_GROUP_WEIGHTS.items()
    }
    remainder = target_count - sum(quotas.values())
    for group in list(DISCOVERY_GROUP_WEIGHTS)[:remainder]:
        quotas[group] += 1
    return quotas


def _group_search_exhausted(group: str, next_pages: dict[str, int]) -> bool:
    keywords = DISCOVERY_KEYWORDS[group]
    return bool(keywords) and all(
        next_pages.get(keyword, 0) >= SEARCH_PAGE_LIMIT for keyword in keywords
    )


def _redistribute_exhausted_quotas(
    quotas: dict[str, int],
    group_counts: Counter[str],
    next_pages: dict[str, int],
) -> None:
    exhausted = [
        group
        for group, quota in quotas.items()
        if group_counts[group] < quota
        and _group_search_exhausted(group, next_pages)
    ]
    if not exhausted:
        return
    target_count = sum(quotas.values())
    previous_quotas = dict(quotas)
    shortfall = 0
    for group in exhausted:
        shortfall += quotas[group] - group_counts[group]
        quotas[group] = group_counts[group]
    max_group_count = max(1, target_count // 2)
    while shortfall:
        eligible = [
            group
            for group, weight in DISCOVERY_GROUP_WEIGHTS.items()
            if weight > 0
            and not _group_search_exhausted(group, next_pages)
            and quotas[group] < max_group_count
        ]
        if not eligible:
            raise ValueError(
                "国内真实商品不足，所有综合电商检索类目均已自然耗尽: "
                + ", ".join(exhausted)
            )
        group = min(
            eligible,
            key=lambda name: (
                quotas[name] / DISCOVERY_GROUP_WEIGHTS[name],
                name,
            ),
        )
        quotas[group] += 1
        shortfall -= 1
    logger.info(
        "重新分配已耗尽类目配额 exhausted=%s old=%s new=%s",
        exhausted,
        previous_quotas,
        quotas,
    )


def _all_text(node: Any, selector: str, limit: int = 512) -> str:
    values = []
    for element in node.css(selector):
        values.extend(element.css("::text").getall())
    return _clean_text(" ".join(values), limit)


def _search_url(keyword: str, page: int) -> str:
    encoded = urllib.parse.quote(keyword, safe="")
    return f"https://search.suning.com/{encoded}/&cp={page}"


def _assert_robots_allowed(client: RateLimitedClient) -> str:
    checks = (
        (
            "https://search.suning.com/robots.txt",
            "https://search.suning.com/%E6%89%8B%E6%9C%BA/&cp=1",
        ),
        (
            "https://product.suning.com/robots.txt",
            "https://product.suning.com/0000000000/12451301248.html",
        ),
    )
    digests = []
    for robots_url, target_url in checks:
        body = client.get(robots_url)
        lines = body.decode("utf-8", errors="replace").splitlines()
        parser = urllib.robotparser.RobotFileParser(robots_url)
        parser.parse(lines)
        if not parser.can_fetch(USER_AGENT, target_url):
            raise ValueError(f"robots.txt不允许采集目标页面: {target_url}")
        digests.append(hashlib.sha256(body).hexdigest())
    return ",".join(digests)


def _parse_search_page(body: bytes, url: str) -> list[SearchCandidate]:
    page = Selector(body, url=url)
    candidates = []
    for item in page.css("#product-list li.item-wrap"):
        raw_key = _clean_text(item.attrib.get("id"), 64)
        if not re.fullmatch(r"[0-9A-Za-z]+-[0-9]+", raw_key):
            continue
        vendor_code, sku_code = raw_key.split("-", maxsplit=1)
        href = item.css(".title-selling-point a::attr(href)").get()
        if not href:
            continue
        source_url = urllib.parse.urljoin(url, str(href))
        candidates.append(SearchCandidate(vendor_code, sku_code, source_url))
    return candidates


def _script_value(script: str, key: str) -> Any:
    marker = f'"{key}"'
    position = script.find(marker)
    if position < 0:
        return None
    colon = script.find(":", position + len(marker))
    if colon < 0:
        return None
    source = script[colon + 1 :].lstrip()
    try:
        return json.JSONDecoder().raw_decode(source)[0]
    except json.JSONDecodeError:
        return None


def _product_script(page: Selector) -> str:
    for script in page.css("script::text").getall():
        if "var sn = sn ||" in script:
            return str(script)
    return ""


def _source_categories(page: Selector) -> tuple[tuple[str, ...], tuple[str, ...]]:
    names = []
    source_ids = []
    seen: set[str] = set()
    for node in page.css(".breadcrumb [gid]"):
        category_id = _clean_text(node.attrib.get("gid"), 32)
        name = _all_text(node, "a", 128) or _all_text(node, "span", 128)
        if not name:
            name = _clean_text(" ".join(node.css("::text").getall()), 128)
        if not category_id or not name or category_id in seen:
            continue
        seen.add(category_id)
        source_ids.append(category_id)
        names.append(name)
        if len(names) == 3:
            break
    return tuple(source_ids), tuple(names)


def _attributes(page: Selector) -> dict[str, str]:
    output: dict[str, str] = {}
    section = ""
    for row in page.css("#itemParameter tr"):
        heading = _all_text(row, "th", 64)
        if heading:
            section = heading
            continue
        name = _all_text(row, "td.name", 128)
        value = _all_text(row, "td.val", 512)
        if not name or not value:
            continue
        key = f"{section}/{name}" if section else name
        output[key] = value
    return output


def _variant_axis_maps(page: Selector) -> list[tuple[str, dict[str, str]]]:
    axes = []
    for node in page.css(".cluster-radio"):
        axis_name = _all_text(node, "dt", 64)
        values: dict[str, str] = {}
        for link in node.css("dd a"):
            onclick = _clean_text(link.attrib.get("onclick"), 512)
            match = re.search(r"changeVersion\('[^']*','[^']*','([^']+)'", onclick)
            label = _clean_text(
                link.attrib.get("title") or " ".join(link.css("::text").getall()),
                128,
            ).strip("【】")
            if match and label:
                values[match.group(1)] = label
        if axis_name and values:
            axes.append((axis_name, values))
    return axes


def _variant_specs(page: Selector, script: str) -> dict[str, dict[str, str]]:
    cluster_map = _script_value(script, "clusterMap")
    axes = _variant_axis_maps(page)
    if isinstance(cluster_map, list) and axes:
        first_axis_name, first_values = axes[0]
        second_axis = axes[1] if len(axes) > 1 else None
        output: dict[str, dict[str, str]] = {}
        for first_group in cluster_map:
            if not isinstance(first_group, dict):
                continue
            first_id = _clean_text(first_group.get("color"), 64)
            items = first_group.get("itemCuPartNumber")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                sku_code = _clean_text(item.get("partNumber"), 32).lstrip("0")
                if not sku_code:
                    continue
                specs = {}
                if first_id in first_values:
                    specs[first_axis_name] = first_values[first_id]
                if second_axis:
                    second_name, second_values = second_axis
                    second_id = _clean_text(item.get("versionId"), 64)
                    if second_id in second_values:
                        specs[second_name] = second_values[second_id]
                output[sku_code] = specs
        if output:
            return output
    return _subcode_variant_specs(page, script)


def _subcode_variant_specs(
    page: Selector, script: str
) -> dict[str, dict[str, str]]:
    g_info = _script_value(script, "gInfo")
    if not isinstance(g_info, dict):
        return {}
    raw_groups = g_info.get("charPartNumbers")
    if not isinstance(raw_groups, list):
        return {}
    axes: list[tuple[str, dict[str, str]]] = []
    for node in page.css("#J-TZM dl.sub-radio"):
        axis_name = _all_text(node, "dt", 64)
        values: dict[str, str] = {}
        for item in node.css("li[cid]"):
            value_id = _clean_text(item.attrib.get("cid"), 64)
            label = _clean_text(
                item.attrib.get("title") or " ".join(item.css("span::text").getall()),
                128,
            )
            if value_id and label:
                values[value_id] = label
        if axis_name and values:
            axes.append((axis_name, values))
    combinations: dict[str, dict[str, str]] = {}
    if axes:
        value_groups = [tuple(values.items()) for _, values in axes]
        for combination in cartesian_product(*value_groups):
            composite_key = "".join(value_id for value_id, _ in combination)
            combinations[composite_key] = {
                axis_name: label
                for (axis_name, _), (_, label) in zip(
                    axes, combination, strict=True
                )
            }
    output: dict[str, dict[str, str]] = {}
    for raw_group in raw_groups:
        if not isinstance(raw_group, dict):
            continue
        for composite_key, raw_item in raw_group.items():
            if not isinstance(raw_item, dict):
                continue
            sku_code = _clean_text(raw_item.get("partNumber"), 32).lstrip("0")
            if not sku_code:
                continue
            specs = dict(combinations.get(str(composite_key), {}))
            axis_name = _clean_text(raw_item.get("characterDisplayName"), 64)
            axis_value = _clean_text(raw_item.get("characterValueDisplayName"), 128)
            if axis_name and axis_value:
                specs.setdefault(axis_name, axis_value)
            output[sku_code] = specs
    return output


def _is_spu_discriminator(axis_name: str) -> bool:
    return any(token in axis_name for token in SPU_DISCRIMINATOR_AXES)


def _filter_variant_specs_to_spu(
    variant_specs: dict[str, dict[str, str]], current_sku: str
) -> dict[str, dict[str, str]]:
    current_specs = variant_specs.get(current_sku, {})
    discriminators = {
        axis_name: value
        for axis_name, value in current_specs.items()
        if _is_spu_discriminator(axis_name)
    }
    if not discriminators:
        return variant_specs
    return {
        sku_code: specs
        for sku_code, specs in variant_specs.items()
        if all(specs.get(axis_name) == value for axis_name, value in discriminators.items())
    }


def _suning_source_key(
    vendor_code: str, brand_id: str, sku_codes: list[str]
) -> str:
    group_material = f"{vendor_code}|{brand_id}|" + ",".join(sorted(sku_codes))
    group_hash = hashlib.sha256(group_material.encode()).hexdigest()[:24]
    return f"{SUNING_ORIGIN_PLATFORM}:{group_hash}"


def _jsonp_payload(body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace").strip()
    start = text.find("(")
    end = text.rfind(")")
    if start < 0 or end <= start:
        raise ValueError("价格接口没有返回JSONP")
    payload = json.loads(text[start + 1 : end])
    if not isinstance(payload, dict):
        raise ValueError("价格接口响应不是对象")
    return payload


def _fetch_prices(
    client: RateLimitedClient,
    sku_codes: list[str],
    vendor_code: str,
    category_group: str,
    brand_id: str,
    referer: str,
) -> dict[str, dict[str, str]]:
    callback = "ds0000000000" + str(random.randint(10_000, 99_999))
    items = []
    for sku_code in sku_codes:
        fields = [sku_code, "", "", "", "", category_group, brand_id, "", ""]
        items.append("_".join(fields))
    encoded_items = ",".join(items)
    url = (
        "https://ds.suning.com/ds/generalForTile/"
        f"{encoded_items}-{PRICE_REGION_CODE}-2-{vendor_code}-1--{callback}.jsonp"
    )
    payload = _jsonp_payload(client.get(url, referer=referer))
    prices: dict[str, dict[str, str]] = {}
    rows = payload.get("rs")
    if not isinstance(rows, list):
        return prices
    for row in rows:
        if not isinstance(row, dict):
            continue
        sku_code = _clean_text(row.get("cmmdtyCode"), 32).lstrip("0")
        sale_price = _clean_text(row.get("price"), 32)
        if not sku_code or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", sale_price):
            continue
        list_price = _clean_text(
            row.get("originalPrice") or row.get("refPrice") or row.get("snPrice"),
            32,
        )
        prices[sku_code] = {
            "sale_price": f"{float(sale_price):.2f}",
            "list_price": f"{float(list_price):.2f}" if list_price else "",
        }
    return prices


def _decimal_source(value: Any, scale: int, maximum: float) -> str | None:
    cleaned = _clean_text(value, 64)
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", cleaned):
        return None
    number = float(cleaned)
    if number <= 0 or number > maximum:
        return None
    return f"{number:.{scale}f}"


def _parse_review_count(value: Any) -> int | None:
    cleaned = _clean_text(value, 32)
    match = re.search(r"[0-9]+", cleaned)
    count = int(match.group()) if match else 0
    return count if count > 0 else None


def _spu_name(title: str, specs: dict[str, str]) -> str:
    output = title
    for value in sorted(specs.values(), key=len, reverse=True):
        output = re.sub(re.escape(value), " ", output, flags=re.IGNORECASE)
    return _clean_text(output, 256) or title


def _normalize_product(
    client: RateLimitedClient,
    candidate: SearchCandidate,
    selection_group: str,
    minimum_sku_count: int = 1,
) -> CatalogProduct | None:
    body = client.get(candidate.source_url, referer=SUNING_REPOSITORY_URL)
    page = Selector(body, url=candidate.source_url)
    script = _product_script(page)
    if not script:
        return None

    title = _clean_text(_script_value(script, "itemDisplayName"), 256)
    brand = _clean_text(_script_value(script, "brandName"), 128)
    brand_id = _clean_text(_script_value(script, "brandId"), 64)
    category_group = _clean_text(_script_value(script, "catenIds"), 64)
    source_ids, source_path = _source_categories(page)
    store = _clean_text(page.css("#shop_name::attr(value)").get(), 128)
    store_id = _clean_text(page.css("#shop_code::attr(value)").get(), 64)
    if not store_id:
        store_id = candidate.vendor_code
    if not all((title, brand, brand_id, category_group, store, source_path)):
        return None

    variant_specs = _variant_specs(page, script)
    current_sku = _clean_text(_script_value(script, "passPartNumber"), 32).lstrip("0")
    if not variant_specs and current_sku:
        variant_specs[current_sku] = {}
    variant_specs = _filter_variant_specs_to_spu(variant_specs, current_sku)
    if not variant_specs:
        return None
    source_skus = sorted(variant_specs)[:MAX_SOURCE_SKUS_PER_SPU]
    if len(source_skus) < minimum_sku_count:
        return None
    normalized_spu_name = _spu_name(title, variant_specs.get(current_sku, {}))
    image_url = _clean_text(_script_value(script, "fristPic"), 1000) or None
    if image_url and image_url.startswith("//"):
        image_url = "https:" + image_url
    subtitle = _all_text(page, "#promotionDesc", 512) or None
    model = _clean_text(_script_value(script, "modelName"), 128) or None
    attributes = _attributes(page)
    if not image_url or not attributes:
        return None
    source_key = _suning_source_key(
        candidate.vendor_code,
        brand_id,
        list(variant_specs),
    )
    if not client.claim_source(source_key):
        return None
    prices: dict[str, dict[str, str]] = {}
    try:
        for start in range(0, len(source_skus), 10):
            prices.update(
                _fetch_prices(
                    client,
                    source_skus[start : start + 10],
                    candidate.vendor_code,
                    category_group,
                    brand_id,
                    candidate.source_url,
                )
            )
    except OSError:
        client.release_source(source_key)
        raise
    selected_skus = [sku_code for sku_code in source_skus if sku_code in prices]
    if len(selected_skus) < minimum_sku_count:
        client.release_source(source_key)
        return None
    skus = []
    for sku_code in selected_skus:
        specs = variant_specs[sku_code]
        suffix = " ".join(f"{key}:{value}" for key, value in specs.items())
        sku_title = _clean_text(f"{normalized_spu_name} {suffix}", 256)
        skus.append(
            CatalogSku(
                source_key=(
                    f"{SUNING_ORIGIN_PLATFORM}:{candidate.vendor_code}:{sku_code}"
                ),
                external_sku_id=sku_code,
                title=sku_title,
                specs=specs,
                sale_price_cny=prices[sku_code]["sale_price"],
                list_price_cny=prices[sku_code]["list_price"] or None,
                price_region_code=PRICE_REGION_CODE,
                image_url=image_url if sku_code == current_sku else None,
                source_url=(
                    "https://product.suning.com/"
                    f"{candidate.vendor_code}/{sku_code}.html"
                ),
            )
        )

    padded_path = list(source_path)
    while len(padded_path) < 3:
        padded_path.append(padded_path[-1])
    return CatalogProduct(
        source_key=source_key,
        external_product_id=(
            f"{candidate.vendor_code}:{current_sku or candidate.sku_code}"
        ),
        origin_platform=SUNING_ORIGIN_PLATFORM,
        source_category=category_group,
        source_category_ids=source_ids,
        title=title,
        spu_name=normalized_spu_name,
        subtitle=subtitle,
        brand=brand,
        source_brand_id=brand_id,
        store=store,
        source_store_id=store_id,
        is_self_operated=candidate.vendor_code == "0000000000",
        is_cross_border=bool(_script_value(script, "hwgShopFlag")),
        root_category=selection_group,
        second_category=padded_path[1],
        leaf_category=padded_path[2],
        source_category_path=source_path,
        attributes=attributes,
        model=model,
        main_image_url=image_url,
        source_weight=_clean_text(_script_value(script, "weight"), 64) or None,
        source_volume=_clean_text(_script_value(script, "volume"), 64) or None,
        weight_kg=_decimal_source(_script_value(script, "weight"), 3, 999.0),
        volume_m3=None,
        review_count=_parse_review_count(_script_value(script, "reviewTotal")),
        source_url=candidate.source_url,
        captured_at=datetime.now(UTC).isoformat(),
        selection_group=selection_group,
        skus=tuple(skus),
    )


def _normalize_candidates(
    client: RateLimitedClient,
    candidates: list[SearchCandidate],
    selection_group: str,
    minimum_sku_count: int = 1,
    ignore_network_errors: bool = False,
) -> list[CatalogProduct | None]:
    def normalize(candidate: SearchCandidate) -> CatalogProduct | None:
        try:
            return _normalize_product(
                client,
                candidate,
                selection_group,
                minimum_sku_count,
            )
        except OSError as error:
            if not ignore_network_errors:
                raise
            logger.warning(
                "SKU关系刷新跳过暂时不可用页面 url=%s error=%s",
                candidate.source_url,
                error,
            )
            return None

    with ThreadPoolExecutor(max_workers=CRAWL_WORKERS) as executor:
        return list(executor.map(normalize, candidates))


def _has_complete_core_fields(product: CatalogProduct) -> bool:
    return bool(
        product.title
        and product.brand
        and product.store
        and len(product.source_category_path) >= 3
        and product.attributes
        and product.main_image_url
        and product.source_url
        and product.skus
    )


def _read_cache(path: Path) -> list[CatalogProduct]:
    products = []
    if not path.exists():
        return products
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                payload["source_category_ids"] = tuple(payload["source_category_ids"])
                payload["source_category_path"] = tuple(payload["source_category_path"])
                payload["skus"] = tuple(
                    CatalogSku(**sku) for sku in payload.pop("skus")
                )
                products.append(CatalogProduct(**payload))
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                raise ValueError(f"商品源缓存无效: {path}:{line_number}") from error
    return products


def _cache_valid(
    metadata_path: Path,
    cache_path: Path,
    target_spu_count: int,
    target_sku_count: int,
) -> bool:
    if not metadata_path.exists() or not cache_path.exists():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return (
        int(metadata.get("schema_version", 0)) == 8
        and int(metadata.get("variant_parser_revision", 0))
        == VARIANT_PARSER_REVISION
        and int(metadata.get("target_spu_count", 0)) == target_spu_count
        and int(metadata.get("target_sku_count", 0)) == target_sku_count
        and int(metadata.get("selected_spus", 0)) == target_spu_count
        and int(metadata.get("selected_skus", 0)) == target_sku_count
        and int(metadata.get("cached_spus", 0)) == target_spu_count
        and int(metadata.get("available_skus", 0)) >= target_sku_count
        and metadata.get("price_region_code") == PRICE_REGION_CODE
        and metadata.get("sha256") == sha256(cache_path)
    )


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"next_pages": {}, "attempted": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise ValueError(f"采集状态文件无效: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"采集状态文件不是对象: {path}")
    return payload


def _append_product(path: Path, product: CatalogProduct) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as target:
        target.write(
            json.dumps(asdict(product), ensure_ascii=False, separators=(",", ":"))
        )
        target.write("\n")


def _rewrite_products(path: Path, products: list[CatalogProduct]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        for product in products:
            target.write(
                json.dumps(asdict(product), ensure_ascii=False, separators=(",", ":"))
            )
            target.write("\n")
    os.replace(temporary, path)


def _cached_product_vendor_sku(product: CatalogProduct) -> tuple[str, str]:
    vendor_code, separator, sku_code = product.external_product_id.partition(":")
    if not separator or not vendor_code or not sku_code:
        raise ValueError(f"苏宁商品外部ID无效: {product.external_product_id}")
    return vendor_code, sku_code


def _product_discriminator_count(product: CatalogProduct) -> int:
    _, current_sku = _cached_product_vendor_sku(product)
    current = next(
        (sku for sku in product.skus if sku.external_sku_id == current_sku),
        None,
    )
    if current is None:
        return 0
    return sum(_is_spu_discriminator(axis_name) for axis_name in current.specs)


def _canonical_product_relation_key(product: CatalogProduct) -> str:
    vendor_code, _ = _cached_product_vendor_sku(product)
    return _suning_source_key(
        vendor_code,
        product.source_brand_id or product.brand,
        [sku.external_sku_id for sku in product.skus],
    )


def _canonical_product_rank(product: CatalogProduct) -> tuple[int, int, str]:
    _, current_sku = _cached_product_vendor_sku(product)
    sku_ids = {sku.external_sku_id for sku in product.skus}
    return (
        current_sku not in sku_ids,
        -_product_discriminator_count(product),
        product.source_key,
    )


def _deduplicate_exact_product_relations(
    products: list[CatalogProduct],
) -> list[CatalogProduct]:
    groups: dict[str, list[CatalogProduct]] = {}
    for product in products:
        groups.setdefault(_canonical_product_relation_key(product), []).append(product)
    return [min(group, key=_canonical_product_rank) for group in groups.values()]


def _canonicalize_source_products(
    products: list[CatalogProduct],
) -> list[CatalogProduct]:
    split_products = []
    for product in products:
        _, current_sku = _cached_product_vendor_sku(product)
        specs = {sku.external_sku_id: sku.specs for sku in product.skus}
        selected_ids = set(_filter_variant_specs_to_spu(specs, current_sku))
        selected_skus = tuple(
            sku for sku in product.skus if sku.external_sku_id in selected_ids
        )
        if not selected_skus:
            continue
        if len(selected_skus) == len(product.skus):
            split_products.append(product)
            continue
        split_products.append(
            replace(
                product,
                source_key=_suning_source_key(
                    _cached_product_vendor_sku(product)[0],
                    product.source_brand_id or product.brand,
                    [sku.external_sku_id for sku in selected_skus],
                ),
                skus=selected_skus,
            )
        )
    deduplicated = _deduplicate_exact_product_relations(split_products)
    owners: dict[str, list[CatalogProduct]] = {}
    for product in deduplicated:
        for sku in product.skus:
            owners.setdefault(sku.source_key, []).append(product)
    removals: dict[str, set[str]] = {}
    for sku_source_key, candidates in owners.items():
        if len(candidates) < 2:
            continue
        sku_code = sku_source_key.rsplit(":", maxsplit=1)[-1]
        owner = min(
            candidates,
            key=lambda product: (
                _cached_product_vendor_sku(product)[1] != sku_code,
                -_product_discriminator_count(product),
                len(product.skus),
                product.source_key,
            ),
        )
        for product in candidates:
            if product is owner:
                continue
            removals.setdefault(product.source_key, set()).add(sku_source_key)
    resolved = []
    for product in deduplicated:
        removed = removals.get(product.source_key, set())
        selected_skus = tuple(
            sku for sku in product.skus if sku.source_key not in removed
        )
        if not selected_skus:
            continue
        if len(selected_skus) == len(product.skus):
            resolved.append(product)
            continue
        resolved.append(
            replace(
                product,
                source_key=_suning_source_key(
                    _cached_product_vendor_sku(product)[0],
                    product.source_brand_id or product.brand,
                    [sku.external_sku_id for sku in selected_skus],
                ),
                skus=selected_skus,
            )
        )
    output = _deduplicate_exact_product_relations(resolved)
    seen_skus: set[str] = set()
    for product in output:
        for sku in product.skus:
            if sku.source_key in seen_skus:
                raise ValueError(f"来源SKU归属仍然重复: {sku.source_key}")
            seen_skus.add(sku.source_key)
    return output


def _load_variant_refresh_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise ValueError(f"SKU关系刷新状态文件无效: {path}") from error
    if int(payload.get("parser_revision", 0)) != VARIANT_PARSER_REVISION:
        return set()
    values = payload.get("refreshed_source_keys", [])
    if not isinstance(values, list):
        raise ValueError(f"SKU关系刷新状态不是列表: {path}")
    return {str(value) for value in values}


def _refresh_cached_variant_relations(
    client: RateLimitedClient,
    products: list[CatalogProduct],
    cache_path: Path,
    state_path: Path,
) -> list[CatalogProduct]:
    refreshed = _load_variant_refresh_state(state_path)
    queue = [
        product
        for product in products
        if len(product.skus) == 1 and product.source_key not in refreshed
    ]
    if not queue:
        return products
    membership: dict[tuple[str, str], str] = {}
    for product in products:
        if len(product.skus) < 2:
            continue
        vendor_code, _ = _cached_product_vendor_sku(product)
        for sku in product.skus:
            membership[(vendor_code, sku.external_sku_id)] = product.source_key
    upgraded_count = 0
    consolidated_count = 0
    scanned_count = 0
    groups = sorted({product.selection_group for product in queue})
    for selection_group in groups:
        group_queue = [
            product for product in queue if product.selection_group == selection_group
        ]
        for start in range(0, len(group_queue), VARIANT_REFRESH_CHECKPOINT):
            active = {product.source_key: product for product in products}
            batch = [
                active[product.source_key]
                for product in group_queue[
                    start : start + VARIANT_REFRESH_CHECKPOINT
                ]
                if product.source_key in active
            ]
            if not batch:
                continue
            candidates = []
            for product in batch:
                vendor_code, sku_code = _cached_product_vendor_sku(product)
                client.release_source(product.source_key)
                candidates.append(
                    SearchCandidate(vendor_code, sku_code, product.source_url)
                )
            normalized = _normalize_candidates(
                client,
                candidates,
                selection_group,
                minimum_sku_count=2,
                ignore_network_errors=True,
            )
            replacements: dict[str, CatalogProduct] = {}
            for old_product, new_product in zip(batch, normalized, strict=True):
                if new_product is None:
                    continue
                replacements[old_product.source_key] = new_product
                vendor_code, _ = _cached_product_vendor_sku(new_product)
                for sku in new_product.skus:
                    membership[(vendor_code, sku.external_sku_id)] = (
                        new_product.source_key
                    )
                upgraded_count += 1
            batch_keys = {product.source_key for product in batch}
            updated_products = []
            for product in products:
                if product.source_key not in batch_keys:
                    updated_products.append(product)
                    continue
                replacement = replacements.get(product.source_key)
                if replacement is not None:
                    updated_products.append(replacement)
                    continue
                vendor_code, sku_code = _cached_product_vendor_sku(product)
                if (vendor_code, sku_code) in membership:
                    consolidated_count += 1
                    continue
                client.claim_source(product.source_key)
                updated_products.append(product)
            products = updated_products
            refreshed.update(product.source_key for product in batch)
            scanned_count += len(batch)
            _rewrite_products(cache_path, products)
            _atomic_json(
                state_path,
                {
                    "schema_version": 1,
                    "parser_revision": VARIANT_PARSER_REVISION,
                    "refreshed_source_keys": sorted(refreshed),
                    "scanned_count": scanned_count,
                    "upgraded_count": upgraded_count,
                    "consolidated_count": consolidated_count,
                    "remaining_single_sku_count": sum(
                        len(product.skus) == 1 for product in products
                    ),
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
            logger.info(
                "刷新真实SKU关系 scanned=%s/%s upgraded=%s consolidated=%s "
                "spus=%s available_skus=%s",
                scanned_count,
                len(queue),
                upgraded_count,
                consolidated_count,
                len(products),
                sum(len(product.skus) for product in products),
            )
    return products


def _select_real_skus(
    products: list[CatalogProduct], target_sku_count: int
) -> list[CatalogProduct]:
    if target_sku_count < len(products):
        raise ValueError("真实SKU目标数不能小于SPU目标数")
    available = sum(len(product.skus) for product in products)
    if available < target_sku_count:
        raise ValueError(
            f"已采商品的真实SKU不足 requested={target_sku_count} available={available}"
        )
    selected_counts = [1] * len(products)
    remaining = target_sku_count - len(products)
    while remaining:
        made_progress = False
        for index, product in enumerate(products):
            if selected_counts[index] >= len(product.skus):
                continue
            selected_counts[index] += 1
            remaining -= 1
            made_progress = True
            if remaining == 0:
                break
        if not made_progress:
            raise ValueError("真实SKU选择过程无法满足目标数量")
    output = []
    for product, count in zip(products, selected_counts, strict=True):
        payload = asdict(product)
        payload["source_category_ids"] = tuple(payload["source_category_ids"])
        payload["source_category_path"] = tuple(payload["source_category_path"])
        payload["skus"] = tuple(product.skus[:count])
        output.append(CatalogProduct(**payload))
    return output


def _prepare_suning_source(
    data_dir: Path,
    target_spu_count: int,
    target_sku_count: int,
    *,
    force: bool = False,
    delay_seconds: float = 0.5,
) -> tuple[Path, dict[str, Any], list[CatalogProduct]]:
    cache_path = data_dir / SOURCE_CACHE
    metadata_path = data_dir / SOURCE_CACHE_METADATA
    state_path = data_dir / SOURCE_CRAWL_STATE
    if not force and _cache_valid(
        metadata_path, cache_path, target_spu_count, target_sku_count
    ):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        cached_products = _read_cache(cache_path)
        return (
            cache_path,
            metadata,
            _select_real_skus(cached_products, target_sku_count),
        )
    variant_state_path = data_dir / SOURCE_VARIANT_STATE
    if force:
        for path in (cache_path, metadata_path, state_path, variant_state_path):
            path.unlink(missing_ok=True)

    if target_sku_count < target_spu_count:
        raise ValueError("真实SKU目标数不能小于SPU目标数")
    cached_products = _read_cache(cache_path)
    products = [
        product for product in cached_products if _has_complete_core_fields(product)
    ]
    if len(products) != len(cached_products):
        logger.info(
            "移除核心字段不完整的来源商品 count=%s",
            len(cached_products) - len(products),
        )
        _rewrite_products(cache_path, products)
    original_spu_count = len(products)
    original_sku_count = sum(len(product.skus) for product in products)
    products = _canonicalize_source_products(products)
    canonical_sku_count = sum(len(product.skus) for product in products)
    if len(products) != original_spu_count or canonical_sku_count != original_sku_count:
        logger.info(
            "标准化SPU粒度 spus=%s->%s skus=%s->%s",
            original_spu_count,
            len(products),
            original_sku_count,
            canonical_sku_count,
        )
        _rewrite_products(cache_path, products)
    if len(products) > target_spu_count:
        raise ValueError("现有商品源缓存超过本次SPU目标，请使用--force-download")

    state = _load_state(state_path)
    next_pages = {
        str(key): int(value) for key, value in dict(state.get("next_pages", {})).items()
    }
    attempted = {str(value) for value in state.get("attempted", [])}
    seen_source_keys = {product.source_key for product in products}
    client = RateLimitedClient(delay_seconds)
    client.claim_sources(seen_source_keys)
    robots_sha256 = _assert_robots_allowed(client)
    products = _refresh_cached_variant_relations(
        client,
        products,
        cache_path,
        variant_state_path,
    )
    refreshed_spu_count = len(products)
    refreshed_sku_count = sum(len(product.skus) for product in products)
    products = _canonicalize_source_products(products)
    if (
        len(products) != refreshed_spu_count
        or sum(len(product.skus) for product in products) != refreshed_sku_count
    ):
        _rewrite_products(cache_path, products)
    seen_source_keys = {product.source_key for product in products}
    client.claim_sources(seen_source_keys)
    group_counts = Counter(product.selection_group for product in products)
    quotas = _target_quotas(target_spu_count)
    variant_upgrade_count = 0

    while (
        len(products) < target_spu_count
        or sum(len(product.skus) for product in products) < target_sku_count
    ):
        if len(products) < target_spu_count:
            _redistribute_exhausted_quotas(quotas, group_counts, next_pages)
        available_skus = sum(len(product.skus) for product in products)
        needs_variant_upgrade = (
            len(products) == target_spu_count and available_skus < target_sku_count
        )
        made_progress = False
        processed_page = False
        queries = sorted(
            DISCOVERY_QUERIES,
            key=lambda query: (
                query.group not in {"手机数码", "家用电器", "电脑办公"},
                query.group,
                query.keyword,
            ),
        )
        for query in queries:
            if quotas[query.group] == 0:
                continue
            if (
                not needs_variant_upgrade
                and group_counts[query.group] >= quotas[query.group]
            ):
                continue
            page_number = next_pages.get(query.keyword, 0)
            if page_number >= SEARCH_PAGE_LIMIT:
                continue
            processed_page = True
            search_url = _search_url(query.keyword, page_number)
            try:
                search_body = client.get(search_url)
            except OSError as error:
                logger.warning("检索页暂时不可用 url=%s error=%s", search_url, error)
                continue
            candidates = _parse_search_page(search_body, search_url)
            if not candidates:
                next_pages[query.keyword] = SEARCH_PAGE_LIMIT
                _atomic_json(
                    state_path,
                    {
                        "schema_version": 1,
                        "next_pages": next_pages,
                        "attempted": sorted(attempted),
                        "selected_spus": len(products),
                        "available_skus": sum(len(row.skus) for row in products),
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                )
                logger.info(
                    "检索词分页耗尽 group=%s keyword=%s page=%s",
                    query.group,
                    query.keyword,
                    page_number,
                )
                continue
            pending_candidates = []
            for candidate in candidates:
                if candidate.key in attempted:
                    continue
                attempted.add(candidate.key)
                pending_candidates.append(candidate)
            try:
                normalized_products = _normalize_candidates(
                    client,
                    pending_candidates,
                    query.group,
                )
            except OSError as error:
                for candidate in pending_candidates:
                    attempted.discard(candidate.key)
                logger.warning(
                    "商品页暂时不可用 keyword=%s page=%s error=%s",
                    query.keyword,
                    page_number,
                    error,
                )
                continue
            page_replaced_product = False
            for candidate, product in zip(
                pending_candidates,
                normalized_products,
                strict=True,
            ):
                if product is None or product.source_key in seen_source_keys:
                    continue
                if len(products) < target_spu_count:
                    if group_counts[query.group] >= quotas[query.group]:
                        continue
                    _append_product(cache_path, product)
                    products.append(product)
                    seen_source_keys.add(product.source_key)
                    group_counts[query.group] += 1
                    made_progress = True
                else:
                    group_indexes = [
                        index
                        for index, existing in enumerate(products)
                        if existing.selection_group == query.group
                    ]
                    if not group_indexes:
                        continue
                    replace_index = min(
                        group_indexes,
                        key=lambda index: len(products[index].skus),
                    )
                    replaced = products[replace_index]
                    if len(product.skus) <= len(replaced.skus):
                        continue
                    products[replace_index] = product
                    seen_source_keys.add(product.source_key)
                    page_replaced_product = True
                    variant_upgrade_count += 1
                    made_progress = True
                    logger.info(
                        "真实SKU容量升级 group=%s old=%s new=%s available=%s/%s",
                        query.group,
                        len(replaced.skus),
                        len(product.skus),
                        sum(len(row.skus) for row in products),
                        target_sku_count,
                    )
                if len(products) % 100 == 0:
                    logger.info(
                        "真实商品采集进度 spus=%s/%s available_skus=%s",
                        len(products),
                        target_spu_count,
                        sum(len(row.skus) for row in products),
                    )
                available_skus = sum(len(row.skus) for row in products)
                if (
                    len(products) == target_spu_count
                    and available_skus >= target_sku_count
                ):
                    break
                if (
                    not needs_variant_upgrade
                    and group_counts[query.group] == quotas[query.group]
                ):
                    break
            if page_replaced_product:
                _rewrite_products(cache_path, products)
            next_pages[query.keyword] = page_number + 1
            _atomic_json(
                state_path,
                {
                    "schema_version": 1,
                    "next_pages": next_pages,
                    "attempted": sorted(attempted),
                    "selected_spus": len(products),
                    "available_skus": sum(len(row.skus) for row in products),
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
            logger.info(
                "检索页处理完成 group=%s keyword=%s page=%s selected=%s/%s",
                query.group,
                query.keyword,
                page_number,
                group_counts[query.group],
                quotas[query.group],
            )
            if (
                len(products) == target_spu_count
                and sum(len(row.skus) for row in products) >= target_sku_count
            ):
                break
        if (
            len(products) == target_spu_count
            and sum(len(row.skus) for row in products) >= target_sku_count
        ):
            break
        if not processed_page:
            exhausted = [
                group
                for group, quota in quotas.items()
                if group_counts[group] < quota
                and all(
                    next_pages.get(query.keyword, 0) >= SEARCH_PAGE_LIMIT
                    for query in DISCOVERY_QUERIES
                    if query.group == group
                )
            ]
            if exhausted:
                raise ValueError(
                    "国内真实商品不足，请扩充检索词或数据源: " + ", ".join(exhausted)
                )
            raise ValueError(
                "真实SKU关系不足: "
                f"requested={target_sku_count} "
                f"available={sum(len(row.skus) for row in products)}"
            )
        if not made_progress:
            logger.info(
                "当前检索页未提升SKU容量 available=%s/%s",
                sum(len(row.skus) for row in products),
                target_sku_count,
            )

    selected_products = _select_real_skus(products, target_sku_count)
    metadata = {
        "schema_version": 8,
        "variant_parser_revision": VARIANT_PARSER_REVISION,
        "dataset": SUNING_DATASET_NAME,
        "dataset_url": SUNING_DATASET_URL,
        "repository_url": SUNING_REPOSITORY_URL,
        "revision": SUNING_REVISION,
        "captured_at": datetime.now(UTC).isoformat(),
        "target_spu_count": target_spu_count,
        "target_sku_count": target_sku_count,
        "selected_spus": len(selected_products),
        "selected_skus": sum(len(product.skus) for product in selected_products),
        "cached_spus": len(products),
        "available_skus": sum(len(product.skus) for product in products),
        "sha256": sha256(cache_path),
        "selection_group_distribution": dict(group_counts),
        "variant_upgrade_count": variant_upgrade_count,
        "request_delay_seconds": delay_seconds,
        "price_region_code": PRICE_REGION_CODE,
        "robots_checked_at": datetime.now(UTC).isoformat(),
        "robots_sha256": robots_sha256,
        "source_fields_required": [
            "商品标题",
            "品牌",
            "店铺",
            "三级类目",
            "当前价格",
            "商品图片",
            "商品参数",
            "真实SKU关系",
        ],
    }
    _atomic_json(metadata_path, metadata)
    client.close()
    return cache_path, metadata, selected_products


def _source_targets(target_spu_count: int, target_sku_count: int) -> dict[str, int]:
    if target_spu_count < 2:
        return {
            "suning_spus": target_spu_count,
            "suning_skus": target_sku_count,
            "dangdang_spus": 0,
        }
    dangdang_spus = max(1, target_spu_count * 25 // 100)
    return {
        "suning_spus": target_spu_count - dangdang_spus,
        "suning_skus": target_sku_count - dangdang_spus,
        "dangdang_spus": dangdang_spus,
    }


def _cross_source_identity(product: CatalogProduct) -> str:
    brand = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", product.brand.casefold())
    model = re.sub(
        r"[^0-9a-z\u4e00-\u9fff]+",
        "",
        (product.model or "").casefold(),
    )
    title = re.sub(
        r"[^0-9a-z\u4e00-\u9fff]+",
        "",
        product.spu_name.casefold(),
    )
    return f"{brand}|{model or title}"


def prepare_source(
    data_dir: Path,
    target_spu_count: int,
    target_sku_count: int,
    *,
    force: bool = False,
    delay_seconds: float = 0.5,
) -> tuple[list[Path], dict[str, Any], list[CatalogProduct]]:
    from .sources.dangdang import prepare_dangdang_source

    targets = _source_targets(target_spu_count, target_sku_count)
    source_paths: list[Path] = []
    source_metadata: list[dict[str, Any]] = []
    products: list[CatalogProduct] = []

    if targets["dangdang_spus"]:
        path, metadata, rows = prepare_dangdang_source(
            data_dir,
            targets["dangdang_spus"],
            force=force,
            delay_seconds=delay_seconds,
        )
        source_paths.append(path)
        source_metadata.append(metadata)
        products.extend(rows)

    path, metadata, rows = _prepare_suning_source(
        data_dir,
        targets["suning_spus"],
        targets["suning_skus"],
        force=force,
        delay_seconds=delay_seconds,
    )
    source_paths.append(path)
    source_metadata.append(metadata)
    products.extend(rows)

    identities: dict[str, CatalogProduct] = {}
    for product in products:
        identity = _cross_source_identity(product)
        previous = identities.get(identity)
        if previous is not None and previous.origin_platform != product.origin_platform:
            raise ValueError(
                f"跨来源商品重复: {previous.source_key} <-> {product.source_key}"
            )
        identities[identity] = product

    if len(products) != target_spu_count:
        raise ValueError(
            f"多来源SPU数量不一致 expected={target_spu_count} actual={len(products)}"
        )
    selected_skus = sum(len(product.skus) for product in products)
    if selected_skus != target_sku_count:
        raise ValueError(
            f"多来源SKU数量不一致 expected={target_sku_count} actual={selected_skus}"
        )
    origin_distribution = Counter(product.origin_platform for product in products)
    return (
        source_paths,
        {
            "schema_version": 1,
            "dataset_name": CATALOG_DATASET_NAME,
            "captured_at": datetime.now(UTC).isoformat(),
            "request_delay_seconds": delay_seconds,
            "origin_distribution": dict(origin_distribution),
            "cross_source_deduplication": "品牌加型号，缺少型号时使用品牌加标准化SPU标题",
            "selection_group_distribution": dict(
                Counter(product.selection_group for product in products)
            ),
            "sources": source_metadata,
        },
        products,
    )
