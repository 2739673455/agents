from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime

from collection.source import CatalogProduct, CatalogSku, _sanitize_product


def _product(skus: tuple[CatalogSku, ...]) -> CatalogProduct:
    return CatalogProduct(
        source_key="SUNING:vendor:relation",
        external_product_id="vendor:100",
        origin_platform="SUNING",
        source_category="100",
        source_category_ids=("1", "2", "3"),
        title="测试手机",
        spu_name="测试手机",
        subtitle=None,
        brand="测试品牌",
        source_brand_id="brand",
        store="测试店铺",
        source_store_id="vendor",
        is_self_operated=False,
        is_cross_border=False,
        root_category="手机数码",
        second_category="手机通讯",
        leaf_category="手机",
        source_category_path=("手机数码", "手机通讯", "手机"),
        attributes={"品牌": "测试品牌"},
        model="T1",
        main_image_url="https://example.com/product.jpg",
        source_weight=None,
        source_volume=None,
        weight_kg=None,
        volume_m3=None,
        review_count=10,
        source_url="https://example.com/product",
        captured_at=datetime.now(UTC).isoformat(),
        selection_group="手机数码",
        skus=skus,
    )


def _sku(
    sku_id: str,
    specs: dict[str, str],
    sale_price: str = "1999.00",
) -> CatalogSku:
    return CatalogSku(
        source_key=f"SUNING:vendor:{sku_id}",
        external_sku_id=sku_id,
        title="来源标题",
        specs=specs,
        sale_price_cny=sale_price,
        list_price_cny="2299.00",
        price_region_code="025",
        image_url=None,
        source_url=f"https://example.com/{sku_id}",
        origin_specs=specs,
    )


class CatalogQualityTest(unittest.TestCase):
    def test_single_sku_without_specs_is_explicitly_normalized(self) -> None:
        product, rejections, removed = _sanitize_product(_product((_sku("100", {}),)))

        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual(product.skus[0].specs, {"规格": "单规格"})
        self.assertEqual(product.skus[0].specs_provenance, "derived_single_sku")
        self.assertEqual(rejections, [])
        self.assertEqual(removed, 0)

    def test_control_text_and_invalid_prices_do_not_enter_catalog(self) -> None:
        valid = _sku("100", {"颜色": "黑色"})
        artifact = _sku("101", {"操作": "加入购物车"})
        invalid_price = replace(
            _sku("102", {"颜色": "白色"}, "0.05"),
            list_price_cny="0.05",
        )
        product, rejections, removed = _sanitize_product(
            _product((valid, artifact, invalid_price))
        )

        self.assertIsNotNone(product)
        assert product is not None
        self.assertEqual([sku.external_sku_id for sku in product.skus], ["100"])
        self.assertEqual(removed, 1)
        self.assertEqual(
            {row["reason"] for row in rejections},
            {"variant_specs_missing", "category_price_out_of_range"},
        )


if __name__ == "__main__":
    unittest.main()
