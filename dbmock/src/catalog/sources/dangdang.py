"""当当公开搜索页商品目录适配器"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.parse
import urllib.robotparser
from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scrapling.parser import Selector

from ..source import (
    USER_AGENT,
    CatalogProduct,
    CatalogSku,
    RateLimitedClient,
    _append_product,
    _atomic_json,
    _clean_text,
    _read_cache,
    _rewrite_products,
    sha256,
)

logger = logging.getLogger(__name__)

DANGDANG_DATASET_NAME = "当当公开商品搜索页"
DANGDANG_DATASET_URL = "https://www.dangdang.com/"
DANGDANG_REPOSITORY_URL = "https://search.dangdang.com/"
DANGDANG_ORIGIN_PLATFORM = "DANGDANG"
DANGDANG_CACHE = Path("source") / "dangdang_products.jsonl"
DANGDANG_CACHE_METADATA = Path("source") / "dangdang_products.meta.json"
DANGDANG_CRAWL_STATE = Path("source") / "dangdang_crawl_state.json"
SEARCH_PAGE_LIMIT = 100


@dataclass(frozen=True, slots=True)
class DangdangCategory:
    code: str
    second_category: str
    leaf_category: str


DANGDANG_CATEGORIES = (
    DangdangCategory("01.03.30.00.00.00", "小说", "中国当代小说"),
    DangdangCategory("01.03.35.00.00.00", "小说", "外国小说"),
    DangdangCategory("01.03.38.00.00.00", "小说", "侦探悬疑推理小说"),
    DangdangCategory("01.03.41.00.00.00", "小说", "科幻小说"),
    DangdangCategory("01.03.51.00.00.00", "小说", "历史小说"),
    DangdangCategory("01.52.06.00.00.00", "科普读物", "百科知识"),
    DangdangCategory("01.52.04.00.00.00", "科普读物", "科学世界"),
    DangdangCategory("01.52.03.00.00.00", "科普读物", "生物世界"),
    DangdangCategory("01.52.01.00.00.00", "科普读物", "宇宙知识"),
    DangdangCategory("01.41.26.00.00.00", "童书", "中国儿童文学"),
    DangdangCategory("01.43.70.00.00.00", "中小学用书", "中小学阅读"),
)


def _search_url(category: DangdangCategory, page: int) -> str:
    query = urllib.parse.urlencode(
        {
            "category_path": category.code,
            "page_index": page,
        }
    )
    return f"{DANGDANG_REPOSITORY_URL}?key=%CD%BC%CA%E9&{query}"


def _assert_robots_allowed(client: RateLimitedClient) -> str:
    robots_url = f"{DANGDANG_REPOSITORY_URL}robots.txt"
    body = client.get(robots_url)
    parser = urllib.robotparser.RobotFileParser(robots_url)
    parser.parse(body.decode("utf-8", errors="replace").splitlines())
    target_url = _search_url(DANGDANG_CATEGORIES[0], 1)
    if not parser.can_fetch(USER_AGENT, target_url):
        raise ValueError(f"robots.txt不允许采集目标页面: {target_url}")
    return hashlib.sha256(body).hexdigest()


def _decimal_price(value: Any) -> str | None:
    match = re.search(r"[0-9]+(?:\.[0-9]+)?", _clean_text(value, 64))
    if not match:
        return None
    number = float(match.group())
    return f"{number:.2f}" if number > 0 else None


def _image_url(item: Any, page_url: str) -> str | None:
    image = item.css("a.pic img").first
    if image is None:
        return None
    value = _clean_text(
        image.attrib.get("data-original") or image.attrib.get("src"),
        1000,
    )
    if not value or "url_none" in value:
        return None
    return urllib.parse.urljoin(page_url, value)


def _review_count(item: Any) -> int | None:
    value = _clean_text(item.css("a.search_comment_num::text").get(), 64)
    match = re.search(r"[0-9]+", value)
    return int(match.group()) if match else None


def _publication_date(item: Any) -> str | None:
    text = " ".join(item.css("p.search_book_author::text").getall())
    match = re.search(r"[12][0-9]{3}-[01][0-9]-[0-3][0-9]", text)
    return match.group() if match else None


def _normalize_item(
    item: Any,
    category: DangdangCategory,
    page_url: str,
    page_text: str,
    captured_at: str,
) -> CatalogProduct | None:
    raw_id = _clean_text(item.attrib.get("id"), 32)
    product_id = raw_id[1:] if raw_id.startswith("p") else ""
    title = _clean_text(
        item.css("p.name a::attr(title)").get() or item.css("p.name a::text").get(),
        256,
    )
    publisher = _clean_text(
        item.css('p.search_book_author a[name="P_cbs"]::attr(title)').get()
        or item.css('p.search_book_author a[name="P_cbs"]::text').get(),
        128,
    )
    author = _clean_text(
        item.css('p.search_book_author a[name="itemlist-author"]::attr(title)').get()
        or item.css('p.search_book_author a[name="itemlist-author"]::text').get(),
        128,
    )
    sale_price = _decimal_price(item.css("span.search_now_price::text").get())
    list_price = _decimal_price(item.css("span.search_pre_price::text").get())
    href = _clean_text(item.css("p.name a::attr(href)").get(), 1000)
    source_url = urllib.parse.urljoin(page_url, href)
    image_url = _image_url(item, page_url)
    cart_href = _clean_text(item.css("a.search_btn_cart::attr(href)").get(), 256)
    has_source_sku_relation = f'"{product_id}":[{product_id}]' in page_text
    if sale_price is None:
        return None
    if not all(
        (
            product_id,
            title,
            publisher,
            source_url,
            image_url,
            "AddToShoppingCart" in cart_href,
            has_source_sku_relation,
        )
    ):
        return None

    attributes = {"出版社": publisher}
    if author:
        attributes["作者"] = author
    publication_date = _publication_date(item)
    if publication_date:
        attributes["出版日期"] = publication_date
    subtitle = _clean_text(" ".join(item.css("p.detail::text").getall()), 512) or None
    source_key = f"{DANGDANG_ORIGIN_PLATFORM}:{product_id}"
    sku = CatalogSku(
        source_key=source_key,
        external_sku_id=product_id,
        title=title,
        specs={},
        sale_price_cny=sale_price,
        list_price_cny=list_price,
        price_region_code=None,
        image_url=image_url,
        source_url=source_url,
    )
    return CatalogProduct(
        source_key=source_key,
        external_product_id=product_id,
        origin_platform=DANGDANG_ORIGIN_PLATFORM,
        source_category=category.code,
        source_category_ids=tuple(category.code.split(".")),
        title=title,
        spu_name=title,
        subtitle=subtitle,
        brand=publisher,
        source_brand_id=None,
        store="当当自营",
        source_store_id=None,
        is_self_operated=True,
        is_cross_border=False,
        root_category="图书文娱",
        second_category=category.second_category,
        leaf_category=category.leaf_category,
        source_category_path=(
            "图书",
            category.second_category,
            category.leaf_category,
        ),
        attributes=attributes,
        model=None,
        main_image_url=image_url,
        source_weight=None,
        source_volume=None,
        weight_kg=None,
        volume_m3=None,
        review_count=_review_count(item),
        source_url=source_url,
        captured_at=captured_at,
        selection_group="图书文娱",
        skus=(sku,),
    )


def _parse_search_page(
    body: bytes,
    category: DangdangCategory,
    url: str,
) -> list[CatalogProduct]:
    page_text = body.decode("gb18030", errors="replace")
    page = Selector(page_text.encode("utf-8"), url=url)
    items = page.css("#component_59 li")
    if not items:
        return []
    captured_at = datetime.now(UTC).isoformat()
    products = []
    for item in items:
        product = _normalize_item(item, category, url, page_text, captured_at)
        if product is not None:
            products.append(product)
    return products


def _category_quotas(target_count: int) -> dict[str, int]:
    quotient, remainder = divmod(target_count, len(DANGDANG_CATEGORIES))
    return {
        category.code: quotient + int(index < remainder)
        for index, category in enumerate(DANGDANG_CATEGORIES)
    }


def _redistribute_quota(
    quotas: dict[str, int],
    counts: Counter[str],
    exhausted_code: str,
    next_pages: dict[str, int],
) -> None:
    deficit = max(0, quotas[exhausted_code] - counts[exhausted_code])
    quotas[exhausted_code] = counts[exhausted_code]
    available = [
        category.code
        for category in DANGDANG_CATEGORIES
        if category.code != exhausted_code
        and next_pages.get(category.code, 1) <= SEARCH_PAGE_LIMIT
    ]
    if not available and deficit:
        raise ValueError("当当图书细分类目总量不足")
    for index in range(deficit):
        quotas[available[index % len(available)]] += 1


def _cache_valid(metadata_path: Path, cache_path: Path, target_count: int) -> bool:
    if not metadata_path.exists() or not cache_path.exists():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return (
        int(metadata.get("schema_version", 0)) == 2
        and int(metadata.get("selected_spus", 0)) == target_count
        and int(metadata.get("selected_skus", 0)) == target_count
        and metadata.get("sha256") == sha256(cache_path)
    )


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"next_pages": {}, "attempted": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise ValueError(f"当当采集状态文件无效: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"当当采集状态文件不是对象: {path}")
    return payload


def prepare_dangdang_source(
    data_dir: Path,
    target_count: int,
    *,
    force: bool = False,
    delay_seconds: float = 0.5,
) -> tuple[Path, dict[str, Any], list[CatalogProduct]]:
    cache_path = data_dir / DANGDANG_CACHE
    metadata_path = data_dir / DANGDANG_CACHE_METADATA
    state_path = data_dir / DANGDANG_CRAWL_STATE
    if not force and _cache_valid(metadata_path, cache_path, target_count):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return cache_path, metadata, _read_cache(cache_path)
    if force:
        for path in (cache_path, metadata_path, state_path):
            path.unlink(missing_ok=True)

    cached_products = _read_cache(cache_path)
    products = [
        replace(product, source_brand_id=None, source_store_id=None)
        for product in cached_products
    ]
    if products != cached_products:
        _rewrite_products(cache_path, products)
    if len(products) > target_count:
        raise ValueError("现有当当商品缓存超过目标，请使用--force-download")
    state = _load_state(state_path)
    next_pages = {
        str(key): int(value) for key, value in dict(state.get("next_pages", {})).items()
    }
    attempted = {str(value) for value in state.get("attempted", [])}
    seen = {product.source_key for product in products}
    counts = Counter(product.source_category for product in products)
    quotas = _category_quotas(target_count)
    for category in DANGDANG_CATEGORIES:
        if next_pages.get(category.code, 1) > SEARCH_PAGE_LIMIT:
            _redistribute_quota(
                quotas,
                counts,
                category.code,
                next_pages,
            )
    client = RateLimitedClient(delay_seconds)
    robots_sha256 = _assert_robots_allowed(client)

    while len(products) < target_count:
        made_progress = False
        for category in DANGDANG_CATEGORIES:
            if counts[category.code] >= quotas[category.code]:
                continue
            page_number = next_pages.get(category.code, 1)
            if page_number > SEARCH_PAGE_LIMIT:
                continue
            url = _search_url(category, page_number)
            page_products = _parse_search_page(client.get(url), category, url)
            if not page_products:
                next_pages[category.code] = SEARCH_PAGE_LIMIT + 1
                _redistribute_quota(
                    quotas,
                    counts,
                    category.code,
                    next_pages,
                )
                _atomic_json(
                    state_path,
                    {
                        "schema_version": 1,
                        "next_pages": next_pages,
                        "attempted": sorted(attempted),
                        "selected_spus": len(products),
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                )
                logger.info(
                    "当当图书细分类目耗尽 category=%s page=%s selected=%s",
                    category.code,
                    page_number,
                    counts[category.code],
                )
                continue
            for product in page_products:
                if product.external_product_id in attempted:
                    continue
                attempted.add(product.external_product_id)
                if product.source_key in seen:
                    continue
                _append_product(cache_path, product)
                products.append(product)
                seen.add(product.source_key)
                counts[category.code] += 1
                made_progress = True
                if (
                    len(products) == target_count
                    or counts[category.code] == quotas[category.code]
                ):
                    break
            next_pages[category.code] = page_number + 1
            _atomic_json(
                state_path,
                {
                    "schema_version": 1,
                    "next_pages": next_pages,
                    "attempted": sorted(attempted),
                    "selected_spus": len(products),
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
            if len(products) == target_count:
                break
        if not made_progress:
            raise ValueError("当当真实商品不足，请扩充公开类目")

    _rewrite_products(cache_path, products)
    metadata = {
        "schema_version": 2,
        "dataset": DANGDANG_DATASET_NAME,
        "dataset_url": DANGDANG_DATASET_URL,
        "repository_url": DANGDANG_REPOSITORY_URL,
        "revision": "live",
        "captured_at": datetime.now(UTC).isoformat(),
        "selected_spus": len(products),
        "selected_skus": len(products),
        "sha256": sha256(cache_path),
        "category_distribution": dict(counts),
        "request_delay_seconds": delay_seconds,
        "robots_checked_at": datetime.now(UTC).isoformat(),
        "robots_sha256": robots_sha256,
        "source_fields_required": [
            "商品ID",
            "商品标题",
            "出版社",
            "自营购物车关系",
            "类目",
            "当前价格",
            "商品图片",
        ],
    }
    _atomic_json(metadata_path, metadata)
    return cache_path, metadata, products
