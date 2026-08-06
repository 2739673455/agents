from typing import Optional
import datetime
import decimal

from sqlalchemy import (
    BigInteger,
    CHAR,
    CheckConstraint,
    Computed,
    DECIMAL,
    Date,
    Index,
    Integer,
    JSON,
    String,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, SMALLINT, TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BridgeCouponScope(Base):
    __tablename__ = "bridge_coupon_scope"
    __table_args__ = (
        CheckConstraint("(`is_excluded` in (0,1))", name="bridge_coupon_scope_chk_1"),
        Index("idx_coupon_scope_target", "scope_type", "scope_business_id"),
        Index(
            "uk_coupon_scope",
            "coupon_template_version_sk",
            "scope_type",
            "scope_business_id",
            unique=True,
        ),
        {"comment": "优惠券规则版本适用范围桥表"},
    )

    coupon_scope_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="优惠券范围关系代理键"
    )
    coupon_template_version_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="优惠券规则版本代理键"
    )
    coupon_template_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="优惠券模板业务ID"
    )
    scope_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="适用对象类型"
    )
    scope_business_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="适用对象业务ID"
    )
    is_excluded: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否排除对象:0否 1是",
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )


class BridgePromotionScope(Base):
    __tablename__ = "bridge_promotion_scope"
    __table_args__ = (
        CheckConstraint(
            "(`is_excluded` in (0,1))", name="bridge_promotion_scope_chk_1"
        ),
        Index("idx_promotion_scope_target", "scope_type", "scope_business_id"),
        Index(
            "uk_promotion_scope",
            "promotion_version_sk",
            "scope_type",
            "scope_business_id",
            unique=True,
        ),
        {"comment": "促销规则版本适用范围桥表"},
    )

    promotion_scope_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="活动范围关系代理键"
    )
    promotion_version_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="促销规则版本代理键"
    )
    promotion_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="促销活动业务ID"
    )
    scope_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="适用对象类型"
    )
    scope_business_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="适用对象业务ID"
    )
    is_excluded: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否排除对象:0否 1是",
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )


class BridgeUserTagRelationZip(Base):
    __tablename__ = "bridge_user_tag_relation_zip"
    __table_args__ = (
        CheckConstraint(
            "((`tag_score` is null) or (`tag_score` between 0 and 1))",
            name="bridge_user_tag_relation_zip_chk_3",
        ),
        CheckConstraint(
            "(`effective_start_time` < `effective_end_time`)",
            name="bridge_user_tag_relation_zip_chk_1",
        ),
        CheckConstraint(
            "(`is_current` in (0,1))", name="bridge_user_tag_relation_zip_chk_2"
        ),
        Index("idx_user_tag_current", "user_id", "user_tag_sk", "is_current"),
        Index(
            "uk_user_tag_start",
            "user_id",
            "user_tag_sk",
            "effective_start_time",
            unique=True,
        ),
        {"comment": "用户与标签多值关系拉链桥表"},
    )

    user_tag_relation_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="用户标签关系代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    user_tag_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="用户标签代理键"
    )
    effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="关系生效时间"
    )
    effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="关系失效时间"
    )
    is_current: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否当前关系:0否 1是",
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    tag_value: Mapped[Optional[str]] = mapped_column(String(256), comment="标签值")
    tag_score: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(10, 6), comment="标签置信度或权重"
    )


class DimBrandInfo(Base):
    __tablename__ = "dim_brand_info"
    __table_args__ = (
        CheckConstraint("(`brand_status` in (0,1))", name="dim_brand_info_chk_1"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_brand_info_chk_2"),
        Index("idx_brand_name", "brand_name"),
        Index("uk_brand_id", "brand_id", unique=True),
        {"comment": "品牌Type 1一致性维度"},
    )

    brand_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="品牌维度代理键"
    )
    brand_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="品牌业务ID"
    )
    brand_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="品牌名称"
    )
    brand_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="状态:0停用 1启用",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    brand_name_en: Mapped[Optional[str]] = mapped_column(
        String(128), comment="品牌英文名"
    )
    brand_alias: Mapped[Optional[str]] = mapped_column(String(128), comment="品牌别名")
    brand_logo_url: Mapped[Optional[str]] = mapped_column(
        String(512), comment="品牌Logo地址"
    )
    brand_story: Mapped[Optional[str]] = mapped_column(String(2000), comment="品牌故事")
    country_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="品牌国家编码"
    )
    country_name: Mapped[Optional[str]] = mapped_column(
        String(64), comment="品牌国家名称"
    )
    first_letter: Mapped[Optional[str]] = mapped_column(CHAR(1), comment="品牌首字母")
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )


class DimCategoryInfoZip(Base):
    __tablename__ = "dim_category_info_zip"
    __table_args__ = (
        CheckConstraint(
            "(`category_level` between 1 and 10)", name="dim_category_info_zip_chk_1"
        ),
        CheckConstraint(
            "(`category_status` in (0,1))", name="dim_category_info_zip_chk_4"
        ),
        CheckConstraint(
            "(`effective_start_time` < `effective_end_time`)",
            name="dim_category_info_zip_chk_2",
        ),
        CheckConstraint("(`is_current` in (0,1))", name="dim_category_info_zip_chk_5"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_category_info_zip_chk_6"),
        CheckConstraint("(`is_leaf` in (0,1))", name="dim_category_info_zip_chk_3"),
        Index(
            "idx_category_effective",
            "category_id",
            "effective_start_time",
            "effective_end_time",
        ),
        Index("idx_category_parent", "parent_category_id"),
        Index("idx_category_root", "root_category_id"),
        Index("uk_category_current", "current_category_id", unique=True),
        Index("uk_category_start", "category_id", "effective_start_time", unique=True),
        {"comment": "商品类目一致性维度拉链表"},
    )

    category_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="类目维度代理键"
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="类目业务ID"
    )
    category_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="类目名称"
    )
    category_level: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), nullable=False, comment="类目层级"
    )
    category_path_ids: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="类目ID完整路径"
    )
    category_path_names: Mapped[str] = mapped_column(
        String(1024), nullable=False, comment="类目名称完整路径"
    )
    is_leaf: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否叶子类目:0否 1是",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("'0'"), comment="排序号"
    )
    category_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="状态:0停用 1启用",
    )
    effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本生效时间"
    )
    effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本失效时间"
    )
    version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="版本号",
    )
    is_current: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否当前版本:0否 1是",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    parent_category_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="父类目业务ID"
    )
    parent_category_name: Mapped[Optional[str]] = mapped_column(
        String(128), comment="父类目名称快照"
    )
    root_category_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="一级类目业务ID"
    )
    root_category_name: Mapped[Optional[str]] = mapped_column(
        String(128), comment="一级类目名称快照"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )
    current_category_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True),
        Computed(
            "((case when (`is_current` = 1) then `category_id` end))", persisted=True
        ),
    )


class DimChannelInfo(Base):
    __tablename__ = "dim_channel_info"
    __table_args__ = (
        CheckConstraint("(`channel_status` in (0,1))", name="dim_channel_info_chk_1"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_channel_info_chk_2"),
        Index("uk_channel_code", "channel_code", unique=True),
        {"comment": "渠道Type 1一致性维度"},
    )

    channel_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="渠道维度代理键"
    )
    channel_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="渠道业务编码"
    )
    channel_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="渠道名称"
    )
    channel_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="状态:0停用 1启用",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    channel_group: Mapped[Optional[str]] = mapped_column(String(32), comment="渠道分组")
    platform_type: Mapped[Optional[str]] = mapped_column(String(32), comment="平台类型")
    traffic_source_type: Mapped[Optional[str]] = mapped_column(
        String(32), comment="流量来源类型"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )


class DimCouponTemplateVersion(Base):
    __tablename__ = "dim_coupon_template_version"
    __table_args__ = (
        CheckConstraint(
            "((`discount_amount` is null) or (`discount_amount` >= 0))",
            name="dim_coupon_template_version_chk_6",
        ),
        CheckConstraint(
            "((`discount_rate` is null) or (`discount_rate` between 0 and 1))",
            name="dim_coupon_template_version_chk_7",
        ),
        CheckConstraint(
            "((`max_discount_amount` is null) or (`max_discount_amount` >= 0))",
            name="dim_coupon_template_version_chk_8",
        ),
        CheckConstraint(
            "((`threshold_amount` is null) or (`threshold_amount` >= 0))",
            name="dim_coupon_template_version_chk_5",
        ),
        CheckConstraint(
            "(`issue_start_time` < `issue_end_time`)",
            name="dim_coupon_template_version_chk_2",
        ),
        CheckConstraint(
            "(`rule_effective_start_time` < `rule_effective_end_time`)",
            name="dim_coupon_template_version_chk_4",
        ),
        CheckConstraint(
            "(`rule_version_no` > 0)", name="dim_coupon_template_version_chk_1"
        ),
        CheckConstraint(
            "(`use_start_time` < `use_end_time`)",
            name="dim_coupon_template_version_chk_3",
        ),
        Index("idx_coupon_issue_time", "issue_start_time", "issue_end_time"),
        Index(
            "idx_coupon_rule_effective",
            "coupon_template_id",
            "rule_effective_start_time",
            "rule_effective_end_time",
        ),
        Index("idx_coupon_use_time", "use_start_time", "use_end_time"),
        Index(
            "uk_coupon_rule_start",
            "coupon_template_id",
            "rule_effective_start_time",
            unique=True,
        ),
        Index(
            "uk_coupon_rule_version",
            "coupon_template_id",
            "rule_version_no",
            unique=True,
        ),
        {"comment": "优惠券模板不可变规则版本维度"},
    )

    coupon_template_version_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="优惠券规则版本代理键"
    )
    coupon_template_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="优惠券模板业务ID"
    )
    rule_version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="优惠券规则业务版本号"
    )
    coupon_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="优惠券名称"
    )
    coupon_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="优惠券类型"
    )
    issue_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="发券开始时间"
    )
    issue_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="发券结束时间"
    )
    use_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="可用开始时间"
    )
    use_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="可用结束时间"
    )
    rule_effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="规则版本生效时间"
    )
    rule_effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="规则版本失效时间"
    )
    coupon_status: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="该规则版本发布状态"
    )
    rule_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="规则内容哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    threshold_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 2), comment="使用门槛金额"
    )
    discount_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 2), comment="固定优惠金额"
    )
    discount_rate: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(10, 6), comment="优惠折扣率"
    )
    max_discount_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 2), comment="最大优惠金额"
    )
    total_issue_limit: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="最大发行量"
    )
    per_user_limit: Mapped[Optional[int]] = mapped_column(
        INTEGER(unsigned=True), comment="单用户领取上限"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )


class DimDate(Base):
    __tablename__ = "dim_date"
    __table_args__ = (
        CheckConstraint("(`calendar_month` between 1 and 12)", name="dim_date_chk_4"),
        CheckConstraint("(`calendar_quarter` between 1 and 4)", name="dim_date_chk_3"),
        CheckConstraint("(`calendar_year` = year(`full_date`))", name="dim_date_chk_2"),
        CheckConstraint(
            "(`date_key` = (((year(`full_date`) * 10000) + (month(`full_date`) * 100)) + dayofmonth(`full_date`)))",
            name="dim_date_chk_1",
        ),
        CheckConstraint("(`day_of_month` between 1 and 31)", name="dim_date_chk_6"),
        CheckConstraint("(`day_of_week` between 1 and 7)", name="dim_date_chk_7"),
        CheckConstraint("(`fiscal_quarter` between 1 and 4)", name="dim_date_chk_8"),
        CheckConstraint("(`is_holiday` in (0,1))", name="dim_date_chk_10"),
        CheckConstraint("(`is_weekend` in (0,1))", name="dim_date_chk_9"),
        CheckConstraint("(`is_workday` in (0,1))", name="dim_date_chk_11"),
        CheckConstraint("(`week_of_year` between 1 and 53)", name="dim_date_chk_5"),
        Index("uk_full_date", "full_date", unique=True),
        {"comment": "公共日期维度"},
    )

    date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, comment="日期键，格式YYYYMMDD"
    )
    full_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="自然日期"
    )
    calendar_year: Mapped[int] = mapped_column(
        SMALLINT(unsigned=True), nullable=False, comment="自然年"
    )
    calendar_quarter: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), nullable=False, comment="自然季度"
    )
    calendar_month: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), nullable=False, comment="自然月"
    )
    year_month_code: Mapped[str] = mapped_column(
        CHAR(7), nullable=False, comment="年月，格式YYYY-MM"
    )
    week_of_year: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), nullable=False, comment="年内周序号"
    )
    day_of_month: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), nullable=False, comment="月内日序号"
    )
    day_of_week: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), nullable=False, comment="周内日序号，1表示周一"
    )
    day_name_cn: Mapped[str] = mapped_column(
        String(8), nullable=False, comment="中文星期名称"
    )
    is_weekend: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否周末:0否 1是",
    )
    is_holiday: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否法定节假日:0否 1是",
    )
    is_workday: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否工作日:0否 1是",
    )
    fiscal_year: Mapped[int] = mapped_column(
        SMALLINT(unsigned=True), nullable=False, comment="财年"
    )
    fiscal_quarter: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), nullable=False, comment="财年季度"
    )
    holiday_name: Mapped[Optional[str]] = mapped_column(
        String(64), comment="节假日名称"
    )


class DimGeoRegionZip(Base):
    __tablename__ = "dim_geo_region_zip"
    __table_args__ = (
        CheckConstraint(
            "(`effective_start_time` < `effective_end_time`)",
            name="dim_geo_region_zip_chk_2",
        ),
        CheckConstraint("(`is_current` in (0,1))", name="dim_geo_region_zip_chk_4"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_geo_region_zip_chk_5"),
        CheckConstraint(
            "(`region_level` between 1 and 5)", name="dim_geo_region_zip_chk_1"
        ),
        CheckConstraint("(`region_status` in (0,1))", name="dim_geo_region_zip_chk_3"),
        Index("idx_parent_region", "parent_region_code"),
        Index(
            "idx_region_effective",
            "region_code",
            "effective_start_time",
            "effective_end_time",
        ),
        Index("idx_region_hierarchy", "province_code", "city_code", "district_code"),
        Index("uk_region_current", "current_region_code", unique=True),
        Index("uk_region_start", "region_code", "effective_start_time", unique=True),
        {"comment": "行政区域一致性维度拉链表"},
    )

    region_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="行政区域维度代理键"
    )
    region_code: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="区域业务编码"
    )
    region_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="区域名称"
    )
    region_level: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        comment="区域级别:1国家 2省 3市 4区县 5街道",
    )
    region_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="状态:0停用 1启用",
    )
    effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本生效时间"
    )
    effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本失效时间"
    )
    version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="版本号",
    )
    is_current: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否当前版本:0否 1是",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    parent_region_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="父级区域编码"
    )
    country_code: Mapped[Optional[str]] = mapped_column(String(20), comment="国家编码")
    country_name: Mapped[Optional[str]] = mapped_column(String(128), comment="国家名称")
    province_code: Mapped[Optional[str]] = mapped_column(String(20), comment="省编码")
    province_name: Mapped[Optional[str]] = mapped_column(String(128), comment="省名称")
    city_code: Mapped[Optional[str]] = mapped_column(String(20), comment="市编码")
    city_name: Mapped[Optional[str]] = mapped_column(String(128), comment="市名称")
    district_code: Mapped[Optional[str]] = mapped_column(String(20), comment="区县编码")
    district_name: Mapped[Optional[str]] = mapped_column(
        String(128), comment="区县名称"
    )
    region_path: Mapped[Optional[str]] = mapped_column(
        String(512), comment="完整区域路径"
    )
    zip_code: Mapped[Optional[str]] = mapped_column(String(16), comment="邮编")
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )
    current_region_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        Computed(
            "((case when (`is_current` = 1) then `region_code` end))", persisted=True
        ),
    )


class DimLogisticsCompany(Base):
    __tablename__ = "dim_logistics_company"
    __table_args__ = (
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_logistics_company_chk_3"),
        CheckConstraint(
            "(`is_trace_supported` in (0,1))", name="dim_logistics_company_chk_1"
        ),
        CheckConstraint(
            "(`logistics_company_status` in (0,1))", name="dim_logistics_company_chk_2"
        ),
        Index("uk_logistics_company_code", "logistics_company_code", unique=True),
        Index("uk_logistics_company_id", "logistics_company_id", unique=True),
        {"comment": "物流公司Type 1一致性维度"},
    )

    logistics_company_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="物流公司维度代理键"
    )
    logistics_company_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="物流公司业务ID"
    )
    logistics_company_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="物流公司编码"
    )
    logistics_company_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="物流公司名称"
    )
    is_trace_supported: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否支持轨迹查询:0否 1是",
    )
    logistics_company_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="状态:0停用 1启用",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    logistics_type: Mapped[Optional[str]] = mapped_column(
        String(32), comment="物流类型"
    )
    service_phone: Mapped[Optional[str]] = mapped_column(String(32), comment="客服电话")
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )


class DimPageInfo(Base):
    __tablename__ = "dim_page_info"
    __table_args__ = (
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_page_info_chk_2"),
        CheckConstraint("(`page_status` in (0,1))", name="dim_page_info_chk_1"),
        Index("idx_page_type", "page_type"),
        Index("uk_page_id", "page_id", unique=True),
        {"comment": "页面Type 1一致性维度"},
    )

    page_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="页面维度代理键"
    )
    page_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="页面业务ID"
    )
    page_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="页面名称"
    )
    page_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="页面类型"
    )
    page_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="状态:0停用 1启用",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    business_domain: Mapped[Optional[str]] = mapped_column(
        String(32), comment="所属业务域"
    )
    page_path_pattern: Mapped[Optional[str]] = mapped_column(
        String(512), comment="页面路径模板"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )


class DimPaymentType(Base):
    __tablename__ = "dim_payment_type"
    __table_args__ = (
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_payment_type_chk_4"),
        CheckConstraint("(`is_installment` in (0,1))", name="dim_payment_type_chk_2"),
        CheckConstraint("(`is_online` in (0,1))", name="dim_payment_type_chk_1"),
        CheckConstraint(
            "(`payment_type_status` in (0,1))", name="dim_payment_type_chk_3"
        ),
        Index("uk_payment_type_code", "payment_type_code", unique=True),
        {"comment": "支付方式Type 1一致性维度"},
    )

    payment_type_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="支付方式维度代理键"
    )
    payment_type_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="支付方式业务编码"
    )
    payment_type_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="支付方式名称"
    )
    is_online: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否线上支付:0否 1是",
    )
    is_installment: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否支持分期:0否 1是",
    )
    payment_type_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="状态:0停用 1启用",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    payment_institution_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="支付机构编码"
    )
    payment_institution_name: Mapped[Optional[str]] = mapped_column(
        String(64), comment="支付机构名称"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )


class DimPromotionRuleVersion(Base):
    __tablename__ = "dim_promotion_rule_version"
    __table_args__ = (
        CheckConstraint(
            "((`discount_amount` is null) or (`discount_amount` >= 0))",
            name="dim_promotion_rule_version_chk_5",
        ),
        CheckConstraint(
            "((`discount_rate` is null) or (`discount_rate` between 0 and 1))",
            name="dim_promotion_rule_version_chk_6",
        ),
        CheckConstraint(
            "((`max_discount_amount` is null) or (`max_discount_amount` >= 0))",
            name="dim_promotion_rule_version_chk_7",
        ),
        CheckConstraint(
            "((`threshold_amount` is null) or (`threshold_amount` >= 0))",
            name="dim_promotion_rule_version_chk_4",
        ),
        CheckConstraint(
            "(`activity_start_time` < `activity_end_time`)",
            name="dim_promotion_rule_version_chk_2",
        ),
        CheckConstraint(
            "(`rule_effective_start_time` < `rule_effective_end_time`)",
            name="dim_promotion_rule_version_chk_3",
        ),
        CheckConstraint(
            "(`rule_version_no` > 0)", name="dim_promotion_rule_version_chk_1"
        ),
        Index(
            "idx_promotion_activity_time", "activity_start_time", "activity_end_time"
        ),
        Index(
            "idx_promotion_rule_effective",
            "promotion_id",
            "rule_effective_start_time",
            "rule_effective_end_time",
        ),
        Index(
            "uk_promotion_rule_start",
            "promotion_id",
            "rule_effective_start_time",
            unique=True,
        ),
        Index(
            "uk_promotion_rule_version", "promotion_id", "rule_version_no", unique=True
        ),
        {"comment": "促销活动不可变规则版本维度"},
    )

    promotion_version_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="促销规则版本代理键"
    )
    promotion_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="促销活动业务ID"
    )
    rule_version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="促销规则业务版本号"
    )
    promotion_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="活动名称"
    )
    promotion_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="活动类型"
    )
    promotion_scene: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="活动场景"
    )
    promotion_priority: Mapped[int] = mapped_column(
        SMALLINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="活动优先级",
    )
    activity_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="活动开始时间"
    )
    activity_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="活动结束时间"
    )
    rule_effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="规则版本生效时间"
    )
    rule_effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="规则版本失效时间"
    )
    sponsor_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="发起方类型"
    )
    promotion_status: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="该规则版本发布状态"
    )
    rule_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="规则内容哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    rule_description: Mapped[Optional[str]] = mapped_column(
        String(2000), comment="规则说明"
    )
    threshold_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 2), comment="优惠门槛金额"
    )
    discount_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 2), comment="固定优惠金额"
    )
    discount_rate: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(10, 6), comment="优惠折扣率"
    )
    max_discount_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 2), comment="最大优惠金额"
    )
    sponsor_business_id: Mapped[Optional[str]] = mapped_column(
        String(64), comment="发起方业务ID"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )


class DimSellerInfoZip(Base):
    __tablename__ = "dim_seller_info_zip"
    __table_args__ = (
        CheckConstraint(
            "(`effective_start_time` < `effective_end_time`)",
            name="dim_seller_info_zip_chk_1",
        ),
        CheckConstraint("(`is_current` in (0,1))", name="dim_seller_info_zip_chk_2"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_seller_info_zip_chk_3"),
        Index(
            "idx_seller_effective",
            "seller_id",
            "effective_start_time",
            "effective_end_time",
        ),
        Index("uk_seller_current", "current_seller_id", unique=True),
        Index("uk_seller_start", "seller_id", "effective_start_time", unique=True),
        {"comment": "商家一致性维度拉链表"},
    )

    seller_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="商家维度代理键"
    )
    seller_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="商家业务ID"
    )
    seller_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="商家名称"
    )
    seller_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'正常'"), comment="商家状态"
    )
    effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本生效时间"
    )
    effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本失效时间"
    )
    version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="版本号",
    )
    is_current: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否当前版本:0否 1是",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    seller_type: Mapped[Optional[str]] = mapped_column(String(32), comment="商家类型")
    industry_type: Mapped[Optional[str]] = mapped_column(String(64), comment="所属行业")
    country_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="注册国家编码"
    )
    province_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="注册省编码"
    )
    city_code: Mapped[Optional[str]] = mapped_column(String(20), comment="注册市编码")
    settle_date: Mapped[Optional[datetime.date]] = mapped_column(
        Date, comment="入驻日期"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )
    current_seller_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True),
        Computed(
            "((case when (`is_current` = 1) then `seller_id` end))", persisted=True
        ),
    )


class DimShopInfoZip(Base):
    __tablename__ = "dim_shop_info_zip"
    __table_args__ = (
        CheckConstraint(
            "(`effective_start_time` < `effective_end_time`)",
            name="dim_shop_info_zip_chk_1",
        ),
        CheckConstraint("(`is_cross_border` in (0,1))", name="dim_shop_info_zip_chk_3"),
        CheckConstraint("(`is_current` in (0,1))", name="dim_shop_info_zip_chk_4"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_shop_info_zip_chk_5"),
        CheckConstraint(
            "(`is_self_operated` in (0,1))", name="dim_shop_info_zip_chk_2"
        ),
        Index(
            "idx_shop_effective",
            "shop_id",
            "effective_start_time",
            "effective_end_time",
        ),
        Index("idx_shop_region", "province_code", "city_code", "district_code"),
        Index("idx_shop_seller", "seller_id"),
        Index("uk_shop_current", "current_shop_id", unique=True),
        Index("uk_shop_start", "shop_id", "effective_start_time", unique=True),
        {"comment": "店铺一致性维度拉链表"},
    )

    shop_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="店铺维度代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    shop_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="店铺名称"
    )
    shop_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="店铺类型"
    )
    seller_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="商家业务ID"
    )
    is_self_operated: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否自营:0否 1是",
    )
    is_cross_border: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否跨境:0否 1是",
    )
    shop_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'营业'"), comment="店铺状态"
    )
    effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本生效时间"
    )
    effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本失效时间"
    )
    version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="版本号",
    )
    is_current: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否当前版本:0否 1是",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    industry_type: Mapped[Optional[str]] = mapped_column(String(64), comment="行业类型")
    open_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="开店时间"
    )
    province_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="店铺省编码"
    )
    city_code: Mapped[Optional[str]] = mapped_column(String(20), comment="店铺市编码")
    district_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="店铺区编码"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )
    current_shop_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True),
        Computed("((case when (`is_current` = 1) then `shop_id` end))", persisted=True),
    )


class DimSkuInfoZip(Base):
    __tablename__ = "dim_sku_info_zip"
    __table_args__ = (
        CheckConstraint(
            "(`effective_start_time` < `effective_end_time`)",
            name="dim_sku_info_zip_chk_1",
        ),
        CheckConstraint("(`is_current` in (0,1))", name="dim_sku_info_zip_chk_2"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_sku_info_zip_chk_3"),
        Index("idx_sku_brand", "brand_id"),
        Index(
            "idx_sku_effective", "sku_id", "effective_start_time", "effective_end_time"
        ),
        Index("idx_sku_shop_category", "shop_id", "category_id"),
        Index("idx_sku_spu", "spu_id"),
        Index("uk_sku_current", "current_sku_id", unique=True),
        Index("uk_sku_start", "sku_id", "effective_start_time", unique=True),
        {"comment": "SKU一致性维度拉链表"},
    )

    sku_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="SKU维度代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SKU业务ID"
    )
    sku_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="SKU名称"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="叶子类目业务ID"
    )
    unit: Mapped[Optional[str]] = mapped_column(String(16), comment="计量单位")
    sku_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'在售'"), comment="SKU状态"
    )
    effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本生效时间"
    )
    effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本失效时间"
    )
    version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="版本号",
    )
    is_current: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否当前版本:0否 1是",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    brand_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="品牌业务ID"
    )
    bar_code: Mapped[Optional[str]] = mapped_column(String(64), comment="商品条码")
    sku_specs_json: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="低频SKU规格属性"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )
    current_sku_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True),
        Computed("((case when (`is_current` = 1) then `sku_id` end))", persisted=True),
    )


class DimSpuInfoZip(Base):
    __tablename__ = "dim_spu_info_zip"
    __table_args__ = (
        CheckConstraint(
            "((`volume_m3` is null) or (`volume_m3` >= 0))",
            name="dim_spu_info_zip_chk_5",
        ),
        CheckConstraint(
            "((`weight_kg` is null) or (`weight_kg` >= 0))",
            name="dim_spu_info_zip_chk_4",
        ),
        CheckConstraint(
            "(`effective_start_time` < `effective_end_time`)",
            name="dim_spu_info_zip_chk_1",
        ),
        CheckConstraint("(`is_current` in (0,1))", name="dim_spu_info_zip_chk_6"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_spu_info_zip_chk_7"),
        CheckConstraint("(`is_presale` in (0,1))", name="dim_spu_info_zip_chk_3"),
        CheckConstraint("(`is_virtual` in (0,1))", name="dim_spu_info_zip_chk_2"),
        Index("idx_spu_brand", "brand_id"),
        Index(
            "idx_spu_effective", "spu_id", "effective_start_time", "effective_end_time"
        ),
        Index("idx_spu_shop_category", "shop_id", "category_id"),
        Index("uk_spu_current", "current_spu_id", unique=True),
        Index("uk_spu_start", "spu_id", "effective_start_time", unique=True),
        {"comment": "SPU一致性维度拉链表"},
    )

    spu_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="SPU维度代理键"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    spu_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="SPU名称"
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="叶子类目业务ID"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    is_virtual: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否虚拟商品:0否 1是",
    )
    is_presale: Mapped[Optional[int]] = mapped_column(
        TINYINT(unsigned=True), comment="是否预售:0否 1是"
    )
    spu_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'在售'"), comment="SPU状态"
    )
    effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本生效时间"
    )
    effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本失效时间"
    )
    version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="版本号",
    )
    is_current: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否当前版本:0否 1是",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    spu_sub_title: Mapped[Optional[str]] = mapped_column(
        String(512), comment="SPU副标题"
    )
    brand_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="品牌业务ID"
    )
    presale_start_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="预售开始时间"
    )
    presale_end_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="预售结束时间"
    )
    weight_kg: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(16, 3), comment="商品重量千克"
    )
    volume_m3: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(16, 6), comment="商品体积立方米"
    )
    on_shelf_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="上架时间"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )
    current_spu_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True),
        Computed("((case when (`is_current` = 1) then `spu_id` end))", persisted=True),
    )


class DimUserInfoZip(Base):
    __tablename__ = "dim_user_info_zip"
    __table_args__ = (
        CheckConstraint(
            "(`effective_start_time` < `effective_end_time`)",
            name="dim_user_info_zip_chk_1",
        ),
        CheckConstraint("(`is_current` in (0,1))", name="dim_user_info_zip_chk_3"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_user_info_zip_chk_4"),
        CheckConstraint("(`is_vip` in (0,1))", name="dim_user_info_zip_chk_2"),
        Index(
            "idx_user_effective",
            "user_id",
            "effective_start_time",
            "effective_end_time",
        ),
        Index("idx_user_region", "province_code", "city_code", "district_code"),
        Index("idx_user_register_time", "register_time"),
        Index("uk_user_current", "current_user_id", unique=True),
        Index("uk_user_start", "user_id", "effective_start_time", unique=True),
        {"comment": "用户一致性维度拉链表"},
    )

    user_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="用户维度代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    gender: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        server_default=text("'未知'"),
        comment="性别:未知/男/女",
    )
    user_level: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'1'"), comment="会员等级"
    )
    is_vip: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否VIP:0否 1是",
    )
    user_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'正常'"), comment="用户状态"
    )
    effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本生效时间"
    )
    effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本失效时间"
    )
    version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="版本号",
    )
    is_current: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否当前版本:0否 1是",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    user_name: Mapped[Optional[str]] = mapped_column(String(64), comment="用户名")
    nick_name: Mapped[Optional[str]] = mapped_column(String(64), comment="昵称")
    birthday: Mapped[Optional[datetime.date]] = mapped_column(Date, comment="生日")
    phone: Mapped[Optional[str]] = mapped_column(String(20), comment="手机号脱敏值")
    email: Mapped[Optional[str]] = mapped_column(String(128), comment="邮箱脱敏值")
    register_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="注册时间"
    )
    register_channel_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="注册渠道编码"
    )
    register_source: Mapped[Optional[str]] = mapped_column(
        String(32), comment="注册来源"
    )
    province_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="常驻省编码"
    )
    city_code: Mapped[Optional[str]] = mapped_column(String(20), comment="常驻市编码")
    district_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="常驻区编码"
    )
    occupation: Mapped[Optional[str]] = mapped_column(String(64), comment="职业")
    income_level: Mapped[Optional[str]] = mapped_column(String(32), comment="收入等级")
    education_level: Mapped[Optional[str]] = mapped_column(
        String(32), comment="学历等级"
    )
    marital_status: Mapped[Optional[str]] = mapped_column(
        String(16), comment="婚姻状态"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )
    current_user_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True),
        Computed("((case when (`is_current` = 1) then `user_id` end))", persisted=True),
    )


class DimUserTagInfo(Base):
    __tablename__ = "dim_user_tag_info"
    __table_args__ = (
        CheckConstraint("(`tag_status` in (0,1))", name="dim_user_tag_info_chk_1"),
        Index("uk_tag_code", "tag_code", unique=True),
        {"comment": "用户标签维度"},
    )

    user_tag_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="用户标签代理键"
    )
    tag_code: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="标签编码"
    )
    tag_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="标签名称"
    )
    tag_value_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'BOOLEAN'"),
        comment="标签值类型",
    )
    tag_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="状态:0停用 1启用",
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    tag_group: Mapped[Optional[str]] = mapped_column(String(64), comment="标签分组")
    tag_description: Mapped[Optional[str]] = mapped_column(
        String(512), comment="标签说明"
    )


class DimWarehouseInfoZip(Base):
    __tablename__ = "dim_warehouse_info_zip"
    __table_args__ = (
        CheckConstraint(
            "(`effective_start_time` < `effective_end_time`)",
            name="dim_warehouse_info_zip_chk_1",
        ),
        CheckConstraint("(`is_current` in (0,1))", name="dim_warehouse_info_zip_chk_3"),
        CheckConstraint("(`is_deleted` in (0,1))", name="dim_warehouse_info_zip_chk_4"),
        CheckConstraint(
            "(`warehouse_status` in (0,1))", name="dim_warehouse_info_zip_chk_2"
        ),
        Index(
            "idx_warehouse_effective",
            "warehouse_id",
            "effective_start_time",
            "effective_end_time",
        ),
        Index("idx_warehouse_region", "province_code", "city_code", "district_code"),
        Index(
            "uk_warehouse_code_start",
            "warehouse_code",
            "effective_start_time",
            unique=True,
        ),
        Index("uk_warehouse_current", "current_warehouse_id", unique=True),
        Index(
            "uk_warehouse_start", "warehouse_id", "effective_start_time", unique=True
        ),
        {"comment": "仓库一致性维度拉链表"},
    )

    warehouse_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="仓库维度代理键"
    )
    warehouse_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="仓库业务ID"
    )
    warehouse_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="仓库编码"
    )
    warehouse_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="仓库名称"
    )
    warehouse_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="仓库类型"
    )
    warehouse_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="状态:0停用 1启用",
    )
    effective_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本生效时间"
    )
    effective_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="版本失效时间"
    )
    version_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="版本号",
    )
    is_current: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="是否当前版本:0否 1是",
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="源记录是否删除:0否 1是",
    )
    attribute_hash: Mapped[str] = mapped_column(
        CHAR(64), nullable=False, comment="业务属性哈希"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="首次入仓时间",
    )
    dw_update_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="最近更新时间",
    )
    owner_type: Mapped[Optional[str]] = mapped_column(
        String(32), comment="仓库归属类型"
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="仓库归属方业务ID"
    )
    country_code: Mapped[Optional[str]] = mapped_column(String(20), comment="国家编码")
    province_code: Mapped[Optional[str]] = mapped_column(String(20), comment="省编码")
    city_code: Mapped[Optional[str]] = mapped_column(String(20), comment="市编码")
    district_code: Mapped[Optional[str]] = mapped_column(String(20), comment="区县编码")
    address: Mapped[Optional[str]] = mapped_column(
        String(512), comment="仓库地址脱敏值"
    )
    source_update_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="源系统更新时间"
    )
    current_warehouse_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True),
        Computed(
            "((case when (`is_current` = 1) then `warehouse_id` end))", persisted=True
        ),
    )


class DwdInteractionCartEventDi(Base):
    __tablename__ = "dwd_interaction_cart_event_di"
    __table_args__ = (
        CheckConstraint(
            "((`sku_unit_price` is null) or (`sku_unit_price` >= 0))",
            name="dwd_interaction_cart_event_di_chk_2",
        ),
        CheckConstraint(
            "(`sku_qty_delta` <> 0)", name="dwd_interaction_cart_event_di_chk_1"
        ),
        Index("idx_cart_session_time", "session_id", "event_time"),
        Index("idx_cart_sku_date", "sku_sk", "biz_date"),
        Index("idx_cart_user_date", "user_sk", "biz_date"),
        Index("uk_cart_event_no", "event_no", unique=True),
        Index(
            "uk_cart_event_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "互动域购物车数量变更事件事实"},
    )

    cart_event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="购物车事件业务ID"
    )
    event_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="事件流水号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="事件时点用户版本代理键",
    )
    device_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="设备ID"
    )
    session_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="会话ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="事件时点店铺版本代理键",
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="事件时点SKU版本代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SKU业务ID"
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="事件时点SPU版本代理键"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    category_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="事件时点类目版本代理键"
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="类目业务ID"
    )
    channel_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("'-1'"), comment="渠道代理键"
    )
    cart_event_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="事件类型:加入/移除/改量/清空"
    )
    sku_qty_delta: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="本次商品数量变化量"
    )
    cart_sku_qty_after: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件后购物车商品数量"
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="事件发生时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取事件发生日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="用户业务ID，游客为空"
    )
    shop_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="店铺业务ID"
    )
    channel_code: Mapped[Optional[str]] = mapped_column(String(32), comment="渠道编码")
    cart_source: Mapped[Optional[str]] = mapped_column(
        String(32), comment="购物车事件来源"
    )
    sku_unit_price: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 4), comment="事件时点商品单价"
    )


class DwdInteractionFavorEventDi(Base):
    __tablename__ = "dwd_interaction_favor_event_di"
    __table_args__ = (
        CheckConstraint(
            "(((`favor_target_type` = _utf8mb4'商品') and (`sku_id` is not null)) or ((`favor_target_type` = _utf8mb4'店铺') and (`shop_id` is not null)))",
            name="dwd_interaction_favor_event_di_chk_1",
        ),
        Index("idx_favor_shop_date", "shop_sk", "biz_date"),
        Index("idx_favor_sku_date", "sku_sk", "biz_date"),
        Index("idx_favor_user_date", "user_sk", "biz_date"),
        Index("uk_favor_event_no", "event_no", unique=True),
        Index(
            "uk_favor_event_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "互动域收藏状态变更事件事实"},
    )

    favor_event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="收藏事件业务ID"
    )
    event_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="事件流水号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="事件时点用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="事件时点店铺版本代理键",
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="事件时点SKU版本代理键",
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="事件时点SPU版本代理键",
    )
    channel_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("'-1'"), comment="渠道代理键"
    )
    favor_target_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="收藏对象类型:商品/店铺"
    )
    favor_event_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="事件类型:收藏/取消收藏"
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="事件发生时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取事件发生日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    device_id: Mapped[Optional[str]] = mapped_column(String(128), comment="设备ID")
    session_id: Mapped[Optional[str]] = mapped_column(String(128), comment="会话ID")
    shop_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="店铺业务ID"
    )
    sku_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="SKU业务ID"
    )
    spu_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="SPU业务ID"
    )
    channel_code: Mapped[Optional[str]] = mapped_column(String(32), comment="渠道编码")


class DwdInventoryChangeDi(Base):
    __tablename__ = "dwd_inventory_change_di"
    __table_args__ = (
        CheckConstraint(
            "((`on_hand_qty_delta` <> 0) or (`reserved_qty_delta` <> 0))",
            name="dwd_inventory_change_di_chk_8",
        ),
        CheckConstraint(
            "((`unit_cost` is null) or (`unit_cost` >= 0))",
            name="dwd_inventory_change_di_chk_9",
        ),
        CheckConstraint(
            "(`after_on_hand_qty` = (`before_on_hand_qty` + `on_hand_qty_delta`))",
            name="dwd_inventory_change_di_chk_1",
        ),
        CheckConstraint(
            "(`after_on_hand_qty` >= 0)", name="dwd_inventory_change_di_chk_4"
        ),
        CheckConstraint(
            "(`after_reserved_qty` <= `after_on_hand_qty`)",
            name="dwd_inventory_change_di_chk_7",
        ),
        CheckConstraint(
            "(`after_reserved_qty` = (`before_reserved_qty` + `reserved_qty_delta`))",
            name="dwd_inventory_change_di_chk_2",
        ),
        CheckConstraint(
            "(`after_reserved_qty` >= 0)", name="dwd_inventory_change_di_chk_6"
        ),
        CheckConstraint(
            "(`before_on_hand_qty` >= 0)", name="dwd_inventory_change_di_chk_3"
        ),
        CheckConstraint(
            "(`before_reserved_qty` >= 0)", name="dwd_inventory_change_di_chk_5"
        ),
        Index("idx_inventory_biz", "biz_type", "biz_id"),
        Index("idx_inventory_sku_date", "sku_sk", "biz_date"),
        Index(
            "idx_inventory_warehouse_sku_time", "warehouse_sk", "sku_sk", "event_time"
        ),
        Index("uk_inventory_change_no", "change_no", unique=True),
        Index(
            "uk_inventory_change_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "库存域库存数量变更事件事实"},
    )

    inventory_change_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="库存变更事件业务ID"
    )
    change_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="库存变更流水号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="变更日期键"
    )
    warehouse_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="变更时仓库版本代理键"
    )
    warehouse_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="仓库业务ID"
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="变更时SKU版本代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SKU业务ID"
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="变更时SPU版本代理键"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="变更时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    change_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="库存变更类型"
    )
    biz_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="关联业务类型"
    )
    biz_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="关联业务单据ID"
    )
    before_on_hand_qty: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="变更前在手库存"
    )
    on_hand_qty_delta: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("'0'"), comment="在手库存变化量"
    )
    after_on_hand_qty: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="变更后在手库存"
    )
    before_reserved_qty: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="变更前预占库存"
    )
    reserved_qty_delta: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("'0'"), comment="预占库存变化量"
    )
    after_reserved_qty: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="变更后预占库存"
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="库存变更时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取库存变更日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    unit_cost: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 4), comment="变更时单位成本"
    )
    total_cost_delta: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 4), comment="库存成本变化金额"
    )
    operator_id: Mapped[Optional[str]] = mapped_column(
        String(64), comment="操作人业务ID"
    )
    operator_type: Mapped[Optional[str]] = mapped_column(
        String(32), comment="操作人类型"
    )
    remark: Mapped[Optional[str]] = mapped_column(String(512), comment="变更说明")


class DwdInventoryDailySnapshotDf(Base):
    __tablename__ = "dwd_inventory_daily_snapshot_df"
    __table_args__ = (
        CheckConstraint(
            "((`inventory_cost_amount` is null) or (`inventory_cost_amount` >= 0))",
            name="dwd_inventory_daily_snapshot_df_chk_4",
        ),
        CheckConstraint(
            "((`unit_cost` is null) or (`unit_cost` >= 0))",
            name="dwd_inventory_daily_snapshot_df_chk_3",
        ),
        CheckConstraint(
            "(`available_qty` = (`on_hand_qty` - `reserved_qty`))",
            name="dwd_inventory_daily_snapshot_df_chk_1",
        ),
        CheckConstraint(
            "(`reserved_qty` <= `on_hand_qty`)",
            name="dwd_inventory_daily_snapshot_df_chk_2",
        ),
        Index("idx_inventory_snapshot_shop_date", "shop_sk", "snapshot_date_key"),
        Index("idx_inventory_snapshot_sku_date", "sku_sk", "snapshot_date_key"),
        Index(
            "uk_inventory_snapshot_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "库存域SKU仓库每日库存周期快照事实"},
    )

    snapshot_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, comment="快照日期键"
    )
    warehouse_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, comment="快照时仓库版本代理键"
    )
    warehouse_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="仓库业务ID"
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, comment="快照时SKU版本代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SKU业务ID"
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="快照时SPU版本代理键"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="快照时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    on_hand_qty: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="期末在手库存"
    )
    reserved_qty: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="期末预占库存"
    )
    available_qty: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="期末可用库存"
    )
    in_transit_qty: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="期末在途库存",
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    snapshot_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="快照时点"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取快照日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    unit_cost: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 4), comment="期末单位成本"
    )
    inventory_cost_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 4), comment="期末库存成本金额"
    )


class DwdMarketingUserCouponEventDi(Base):
    __tablename__ = "dwd_marketing_user_coupon_event_di"
    __table_args__ = (
        CheckConstraint(
            "(`event_seq_no` > 0)", name="dwd_marketing_user_coupon_event_di_chk_1"
        ),
        Index("idx_coupon_template_user", "coupon_template_version_sk", "user_sk"),
        Index("idx_user_coupon_event_date", "biz_date", "coupon_event_type"),
        Index(
            "uk_user_coupon_event_seq", "user_coupon_id", "event_seq_no", unique=True
        ),
        Index(
            "uk_user_coupon_event_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "营销域用户优惠券生命周期事件事实"},
    )

    user_coupon_event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="用户券事件业务ID"
    )
    user_coupon_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户优惠券实例ID"
    )
    event_seq_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="用户券实例内事件序号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    coupon_template_version_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="事件命中的优惠券规则版本代理键"
    )
    coupon_template_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="优惠券模板业务ID"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="事件时点用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    after_coupon_status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="变更后用户券状态"
    )
    coupon_event_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="事件类型:领取/锁定/使用/释放/过期/作废"
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="事件发生时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取事件发生日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    before_coupon_status: Mapped[Optional[str]] = mapped_column(
        String(32), comment="变更前用户券状态"
    )
    related_order_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="关联订单业务ID"
    )
    coupon_batch_no: Mapped[Optional[str]] = mapped_column(
        String(64), comment="发券批次号"
    )


class DwdProductShopScoreDailySnapshotDf(Base):
    __tablename__ = "dwd_product_shop_score_daily_snapshot_df"
    __table_args__ = (
        CheckConstraint(
            "((`description_score` is null) or (`description_score` between 0 and 5))",
            name="dwd_product_shop_score_daily_snapshot_df_chk_3",
        ),
        CheckConstraint(
            "((`logistics_score` is null) or (`logistics_score` between 0 and 5))",
            name="dwd_product_shop_score_daily_snapshot_df_chk_2",
        ),
        CheckConstraint(
            "((`service_score` is null) or (`service_score` between 0 and 5))",
            name="dwd_product_shop_score_daily_snapshot_df_chk_1",
        ),
        Index("idx_shop_score_seller_date", "seller_sk", "snapshot_date_key"),
        Index("idx_shop_score_shop_date", "shop_sk", "snapshot_date_key"),
        Index(
            "uk_shop_score_snapshot_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "商品域店铺服务评分每日周期快照事实"},
    )

    snapshot_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, comment="快照日期键"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="快照时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="店铺业务ID"
    )
    seller_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="快照时商家版本代理键",
    )
    snapshot_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="快照时点"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取快照日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    seller_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="商家业务ID"
    )
    service_score: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(4, 2), comment="服务评分"
    )
    logistics_score: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(4, 2), comment="物流评分"
    )
    description_score: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(4, 2), comment="描述评分"
    )


class DwdProductSkuOperationDailySnapshotDf(Base):
    __tablename__ = "dwd_product_sku_operation_daily_snapshot_df"
    __table_args__ = (
        CheckConstraint(
            "(`is_hot_sale` in (0,1))",
            name="dwd_product_sku_operation_daily_snapshot_df_chk_1",
        ),
        CheckConstraint(
            "(`is_new` in (0,1))",
            name="dwd_product_sku_operation_daily_snapshot_df_chk_2",
        ),
        Index("idx_sku_operation_category_date", "category_sk", "snapshot_date_key"),
        Index("idx_sku_operation_shop_date", "shop_sk", "snapshot_date_key"),
        Index("idx_sku_operation_sku_date", "sku_sk", "snapshot_date_key"),
        Index(
            "uk_sku_operation_snapshot_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "商品域SKU运营属性每日周期快照事实"},
    )

    snapshot_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, comment="快照日期键"
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="快照时SKU版本代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="SKU业务ID"
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="快照时SPU版本代理键"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="快照时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    category_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="快照时叶子类目版本代理键"
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="叶子类目业务ID"
    )
    warning_stock_qty: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="SKU级运营预警库存量",
    )
    is_hot_sale: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="运营口径是否热销:0否 1是",
    )
    is_new: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="运营口径是否新品:0否 1是",
    )
    snapshot_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="快照时点"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取快照日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )


class DwdProductSkuPriceChangeDi(Base):
    __tablename__ = "dwd_product_sku_price_change_di"
    __table_args__ = (
        CheckConstraint(
            "((`new_cost_price` is null) or (`new_cost_price` >= 0))",
            name="dwd_product_sku_price_change_di_chk_6",
        ),
        CheckConstraint(
            "((`previous_cost_price` is null) or (`previous_cost_price` >= 0))",
            name="dwd_product_sku_price_change_di_chk_3",
        ),
        CheckConstraint(
            "((`previous_list_price` is null) or (`previous_list_price` >= 0))",
            name="dwd_product_sku_price_change_di_chk_1",
        ),
        CheckConstraint(
            "((`previous_sale_price` is null) or (`previous_sale_price` >= 0))",
            name="dwd_product_sku_price_change_di_chk_2",
        ),
        CheckConstraint(
            "(`new_list_price` >= 0)", name="dwd_product_sku_price_change_di_chk_4"
        ),
        CheckConstraint(
            "(`new_sale_price` >= 0)", name="dwd_product_sku_price_change_di_chk_5"
        ),
        Index("idx_shop_price_date", "shop_sk", "biz_date"),
        Index("idx_sku_price_effective", "sku_sk", "price_effective_time"),
        Index(
            "uk_sku_price_source", "source_system_code", "source_record_id", unique=True
        ),
        {"comment": "商品域SKU基础价格变更事件事实"},
    )

    price_change_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="价格变更事件业务ID"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="价格生效日期键"
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="价格生效时SKU版本代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SKU业务ID"
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="价格生效时SPU版本代理键"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="价格生效时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    category_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="价格生效时类目版本代理键"
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="类目业务ID"
    )
    brand_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="价格生效时品牌代理键",
    )
    new_list_price: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 4), nullable=False, comment="变更后吊牌单价"
    )
    new_sale_price: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 4), nullable=False, comment="变更后销售单价"
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    price_effective_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="新价格生效时间"
    )
    change_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="价格配置变更时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取新价格生效日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    brand_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="品牌业务ID"
    )
    previous_list_price: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 4), comment="变更前吊牌单价"
    )
    previous_sale_price: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 4), comment="变更前销售单价"
    )
    previous_cost_price: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 4), comment="变更前标准成本单价"
    )
    new_cost_price: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 4), comment="变更后标准成本单价"
    )
    change_reason_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="价格变更原因编码"
    )
    change_reason_description: Mapped[Optional[str]] = mapped_column(
        String(512), comment="价格变更原因说明"
    )


class DwdServiceCommentDetailDi(Base):
    __tablename__ = "dwd_service_comment_detail_di"
    __table_args__ = (
        CheckConstraint(
            "(((`comment_type` = _utf8mb4'初评') and (`parent_comment_detail_id` is null)) or ((`comment_type` = _utf8mb4'追评') and (`parent_comment_detail_id` is not null)))",
            name="dwd_service_comment_detail_di_chk_6",
        ),
        CheckConstraint(
            "((`comment_level` is null) or (`comment_level` between 1 and 5))",
            name="dwd_service_comment_detail_di_chk_1",
        ),
        CheckConstraint(
            "((`description_score` is null) or (`description_score` between 1 and 5))",
            name="dwd_service_comment_detail_di_chk_4",
        ),
        CheckConstraint(
            "((`logistics_score` is null) or (`logistics_score` between 1 and 5))",
            name="dwd_service_comment_detail_di_chk_3",
        ),
        CheckConstraint(
            "((`service_score` is null) or (`service_score` between 1 and 5))",
            name="dwd_service_comment_detail_di_chk_2",
        ),
        CheckConstraint(
            "(`is_anonymous` in (0,1))", name="dwd_service_comment_detail_di_chk_5"
        ),
        Index("idx_comment_order_detail", "order_id", "order_detail_id"),
        Index("idx_comment_shop_date", "shop_sk", "biz_date"),
        Index("idx_comment_sku_date", "sku_sk", "biz_date"),
        Index("idx_comment_topic_time", "comment_id", "comment_time"),
        Index(
            "uk_comment_source", "source_system_code", "source_record_id", unique=True
        ),
        {"comment": "服务域评价内容事件事实"},
    )

    comment_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="评价内容事件业务ID"
    )
    comment_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="评价主题业务ID"
    )
    comment_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="评价类型:初评/追评"
    )
    comment_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="评价日期键"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    order_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单明细业务ID"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="评价时用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="评价时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="评价时SKU版本代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SKU业务ID"
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="评价时SPU版本代理键"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    category_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="评价时类目版本代理键"
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="类目业务ID"
    )
    is_anonymous: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否匿名:0否 1是",
    )
    image_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="图片数量",
    )
    video_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="视频数量",
    )
    comment_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="评价发布时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取评价发布日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    parent_comment_detail_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="关联初评内容事件ID"
    )
    comment_level: Mapped[Optional[int]] = mapped_column(
        TINYINT(unsigned=True), comment="综合评分，追评可为空"
    )
    comment_content: Mapped[Optional[str]] = mapped_column(
        String(2000), comment="评价内容脱敏值"
    )
    service_score: Mapped[Optional[int]] = mapped_column(
        TINYINT(unsigned=True), comment="服务评分"
    )
    logistics_score: Mapped[Optional[int]] = mapped_column(
        TINYINT(unsigned=True), comment="物流评分"
    )
    description_score: Mapped[Optional[int]] = mapped_column(
        TINYINT(unsigned=True), comment="描述评分"
    )
    sensitive_tag: Mapped[Optional[str]] = mapped_column(
        String(128), comment="敏感标签"
    )
    sentiment: Mapped[Optional[str]] = mapped_column(String(16), comment="情感分析结果")


class DwdTradeDeliveryDi(Base):
    __tablename__ = "dwd_trade_delivery_di"
    __table_args__ = (
        CheckConstraint(
            "(`package_freight_amount` >= 0)", name="dwd_trade_delivery_di_chk_2"
        ),
        CheckConstraint(
            "(`package_weight_kg` >= 0)", name="dwd_trade_delivery_di_chk_1"
        ),
        Index("idx_delivery_logistics_date", "logistics_company_sk", "biz_date"),
        Index("idx_delivery_order", "order_id"),
        Index("idx_delivery_refund", "refund_no"),
        Index("idx_delivery_tracking", "tracking_no"),
        Index("idx_delivery_warehouse_date", "warehouse_sk", "biz_date"),
        Index("uk_delivery_package", "package_no", unique=True),
        Index(
            "uk_delivery_source", "source_system_code", "source_record_id", unique=True
        ),
        {"comment": "履约域物流包裹事务事实"},
    )

    delivery_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="物流包裹业务ID"
    )
    delivery_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="物流单号"
    )
    package_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="包裹编号"
    )
    delivery_direction: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="物流方向:正向/逆向"
    )
    delivery_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="包裹创建日期键"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="包裹创建时用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="包裹创建时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    seller_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="包裹创建时商家版本代理键",
    )
    warehouse_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="出入库仓库版本代理键"
    )
    warehouse_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="仓库业务ID"
    )
    logistics_company_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="物流公司代理键",
    )
    receiver_region_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="收件区县版本代理键",
    )
    delivery_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="配送类型"
    )
    package_weight_kg: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 3),
        nullable=False,
        server_default=text("'0.000'"),
        comment="包裹重量千克",
    )
    package_freight_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="包裹运费金额",
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    delivery_create_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="包裹创建时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取包裹创建日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    refund_no: Mapped[Optional[str]] = mapped_column(String(64), comment="关联退款单号")
    seller_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="商家业务ID"
    )
    logistics_company_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="物流公司业务ID"
    )
    receiver_region_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="收件区县编码"
    )
    tracking_no: Mapped[Optional[str]] = mapped_column(String(128), comment="运单号")
    receiver_name: Mapped[Optional[str]] = mapped_column(
        String(64), comment="收件人脱敏值"
    )
    receiver_phone: Mapped[Optional[str]] = mapped_column(
        String(20), comment="收件电话脱敏值"
    )
    receiver_address: Mapped[Optional[str]] = mapped_column(
        String(512), comment="收件地址脱敏值"
    )


class DwdTradeDeliveryItemDi(Base):
    __tablename__ = "dwd_trade_delivery_item_di"
    __table_args__ = (
        CheckConstraint(
            "(`allocated_freight_amount` >= 0)", name="dwd_trade_delivery_item_di_chk_3"
        ),
        CheckConstraint(
            "(`allocated_weight_kg` >= 0)", name="dwd_trade_delivery_item_di_chk_2"
        ),
        CheckConstraint(
            "(`delivery_sku_qty` > 0)", name="dwd_trade_delivery_item_di_chk_1"
        ),
        Index("idx_delivery_item_delivery", "delivery_id"),
        Index("idx_delivery_item_order", "order_id", "order_detail_id"),
        Index("idx_delivery_item_refund", "refund_detail_id"),
        Index("idx_delivery_item_sku_date", "sku_sk", "biz_date"),
        Index(
            "uk_delivery_item_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "履约域物流包裹商品明细事实"},
    )

    delivery_item_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="包裹商品明细业务ID"
    )
    delivery_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="物流包裹业务ID"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    order_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单明细业务ID"
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="包裹创建时SKU版本代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SKU业务ID"
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="包裹创建时SPU版本代理键"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    category_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="包裹创建时类目版本代理键"
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="类目业务ID"
    )
    delivery_sku_qty: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="本包裹商品件数"
    )
    allocated_weight_kg: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 3),
        nullable=False,
        server_default=text("'0.000'"),
        comment="商品分摊重量千克",
    )
    allocated_freight_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="商品分摊运费金额",
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    delivery_create_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="包裹创建时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取包裹创建日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    refund_detail_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="退款明细业务ID"
    )


class DwdTradeDeliveryStatusEventDi(Base):
    __tablename__ = "dwd_trade_delivery_status_event_di"
    __table_args__ = (
        CheckConstraint(
            "(`event_seq_no` > 0)", name="dwd_trade_delivery_status_event_di_chk_1"
        ),
        Index("idx_delivery_status_date", "biz_date", "after_delivery_status"),
        Index("idx_delivery_status_time", "delivery_id", "event_time"),
        Index("uk_delivery_status_seq", "delivery_id", "event_seq_no", unique=True),
        Index(
            "uk_delivery_status_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "履约域物流状态迁移事件事实"},
    )

    delivery_status_event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="物流状态事件业务ID"
    )
    delivery_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="物流包裹业务ID"
    )
    event_seq_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="包裹内事件序号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    after_delivery_status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="变更后物流状态"
    )
    status_event_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="物流事件编码"
    )
    event_region_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="事件地点区域版本代理键",
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="状态变更时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取状态变更日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    before_delivery_status: Mapped[Optional[str]] = mapped_column(
        String(32), comment="变更前物流状态"
    )
    event_region_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="事件地点区域编码"
    )
    event_location: Mapped[Optional[str]] = mapped_column(
        String(256), comment="事件地点说明"
    )
    event_remark: Mapped[Optional[str]] = mapped_column(
        String(512), comment="物流事件说明"
    )


class DwdTradeOrderDetailActivityDi(Base):
    __tablename__ = "dwd_trade_order_detail_activity_di"
    __table_args__ = (
        CheckConstraint(
            "(`promotion_discount_amount` > 0)",
            name="dwd_trade_order_detail_activity_di_chk_1",
        ),
        Index("idx_activity_order", "order_id"),
        Index("idx_activity_promotion_date", "promotion_version_sk", "biz_date"),
        Index(
            "uk_order_activity_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        Index(
            "uk_order_detail_promotion",
            "order_detail_id",
            "promotion_version_sk",
            unique=True,
        ),
        {"comment": "交易域订单明细活动优惠分摊事实"},
    )

    order_detail_activity_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="订单活动分摊业务ID"
    )
    order_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单明细业务ID"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    promotion_version_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="下单命中的促销规则版本代理键"
    )
    promotion_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="促销活动业务ID"
    )
    promotion_discount_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2), nullable=False, comment="活动优惠分摊金额"
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    order_create_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="下单时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取下单日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    rule_snapshot_json: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="命中规则快照"
    )


class DwdTradeOrderDetailCouponDi(Base):
    __tablename__ = "dwd_trade_order_detail_coupon_di"
    __table_args__ = (
        CheckConstraint(
            "((`coupon_receive_time` is null) or (`coupon_receive_time` <= `coupon_use_time`))",
            name="dwd_trade_order_detail_coupon_di_chk_2",
        ),
        CheckConstraint(
            "(`coupon_discount_amount` > 0)",
            name="dwd_trade_order_detail_coupon_di_chk_1",
        ),
        Index("idx_coupon_order", "order_id"),
        Index("idx_coupon_template_date", "coupon_template_version_sk", "biz_date"),
        Index("idx_user_coupon", "user_coupon_id"),
        Index(
            "uk_order_coupon_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        Index(
            "uk_order_detail_user_coupon",
            "order_detail_id",
            "user_coupon_id",
            unique=True,
        ),
        {"comment": "交易域订单明细优惠券优惠分摊事实"},
    )

    order_detail_coupon_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="订单优惠券分摊业务ID"
    )
    order_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单明细业务ID"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    coupon_template_version_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="用券命中的优惠券规则版本代理键"
    )
    coupon_template_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="优惠券模板业务ID"
    )
    user_coupon_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户优惠券实例ID"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="用券时用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    coupon_discount_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2), nullable=False, comment="优惠券优惠分摊金额"
    )
    coupon_use_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="用券时间"
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    order_create_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="下单时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取下单日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    coupon_batch_no: Mapped[Optional[str]] = mapped_column(
        String(64), comment="发券批次号"
    )
    coupon_receive_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DATETIME(fsp=6), comment="领券时间"
    )


class DwdTradeOrderDetailDi(Base):
    __tablename__ = "dwd_trade_order_detail_di"
    __table_args__ = (
        CheckConstraint(
            "((`cost_amount` is null) or (`cost_amount` >= 0))",
            name="dwd_trade_order_detail_di_chk_17",
        ),
        CheckConstraint(
            "(`activity_discount_amount` >= 0)", name="dwd_trade_order_detail_di_chk_11"
        ),
        CheckConstraint(
            "(`coupon_discount_amount` >= 0)", name="dwd_trade_order_detail_di_chk_12"
        ),
        CheckConstraint(
            "(`freight_amount` >= 0)", name="dwd_trade_order_detail_di_chk_14"
        ),
        CheckConstraint(
            "(`is_cross_border` in (0,1))", name="dwd_trade_order_detail_di_chk_2"
        ),
        CheckConstraint(
            "(`is_first_order` in (0,1))", name="dwd_trade_order_detail_di_chk_1"
        ),
        CheckConstraint("(`is_gift` in (0,1))", name="dwd_trade_order_detail_di_chk_4"),
        CheckConstraint(
            "(`is_presale` in (0,1))", name="dwd_trade_order_detail_di_chk_3"
        ),
        CheckConstraint(
            "(`is_risk_order` in (0,1))", name="dwd_trade_order_detail_di_chk_5"
        ),
        CheckConstraint(
            "(`list_amount` = round((`sku_list_unit_price` * `sku_qty`),2))",
            name="dwd_trade_order_detail_di_chk_18",
        ),
        CheckConstraint("(`list_amount` >= 0)", name="dwd_trade_order_detail_di_chk_9"),
        CheckConstraint(
            "(`points_discount_amount` >= 0)", name="dwd_trade_order_detail_di_chk_13"
        ),
        CheckConstraint(
            "(`receivable_amount` = (((((`sale_amount` - `activity_discount_amount`) - `coupon_discount_amount`) - `points_discount_amount`) + `freight_amount`) + `tax_amount`))",
            name="dwd_trade_order_detail_di_chk_20",
        ),
        CheckConstraint(
            "(`receivable_amount` >= 0)", name="dwd_trade_order_detail_di_chk_16"
        ),
        CheckConstraint(
            "(`sale_amount` = round((`sku_sale_unit_price` * `sku_qty`),2))",
            name="dwd_trade_order_detail_di_chk_19",
        ),
        CheckConstraint(
            "(`sale_amount` >= 0)", name="dwd_trade_order_detail_di_chk_10"
        ),
        CheckConstraint(
            "(`sku_list_unit_price` >= 0)", name="dwd_trade_order_detail_di_chk_7"
        ),
        CheckConstraint("(`sku_qty` > 0)", name="dwd_trade_order_detail_di_chk_6"),
        CheckConstraint(
            "(`sku_sale_unit_price` >= 0)", name="dwd_trade_order_detail_di_chk_8"
        ),
        CheckConstraint("(`tax_amount` >= 0)", name="dwd_trade_order_detail_di_chk_15"),
        Index("idx_order_category_date", "category_sk", "biz_date"),
        Index("idx_order_date_shop", "biz_date", "shop_sk"),
        Index("idx_order_id", "order_id"),
        Index("idx_order_sku_date", "sku_sk", "biz_date"),
        Index("idx_order_user_date", "user_sk", "biz_date"),
        Index(
            "uk_order_source_record",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "交易域下单明细事务事实"},
    )

    order_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="订单明细业务ID"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    order_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="订单编号"
    )
    order_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="下单日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="下单时用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="下单时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    seller_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="下单时商家版本代理键",
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="下单时SKU版本代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SKU业务ID"
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="下单时SPU版本代理键"
    )
    spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SPU业务ID"
    )
    category_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="下单时叶子类目版本代理键"
    )
    category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="叶子类目业务ID"
    )
    brand_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("'-1'"), comment="品牌代理键"
    )
    receiver_region_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="收货区县版本代理键",
    )
    channel_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="下单渠道代理键",
    )
    order_scene: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'普通'"), comment="订单场景"
    )
    is_first_order: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否用户首单:0否 1是",
    )
    is_cross_border: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否跨境订单:0否 1是",
    )
    is_presale: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否预售订单:0否 1是",
    )
    is_gift: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否赠品:0否 1是",
    )
    is_risk_order: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否风险订单:0否 1是",
    )
    sku_qty: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="购买件数"
    )
    sku_list_unit_price: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 4), nullable=False, comment="商品吊牌单价快照"
    )
    sku_sale_unit_price: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 4), nullable=False, comment="商品销售单价快照"
    )
    list_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2), nullable=False, comment="吊牌金额"
    )
    sale_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2), nullable=False, comment="优惠前销售金额"
    )
    activity_discount_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="活动优惠分摊金额",
    )
    coupon_discount_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="优惠券优惠分摊金额",
    )
    points_discount_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="积分优惠分摊金额",
    )
    freight_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="运费分摊金额",
    )
    tax_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="税费分摊金额",
    )
    receivable_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2), nullable=False, comment="下单应收金额"
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    order_create_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="下单时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取下单日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    parent_order_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="父订单业务ID"
    )
    trade_no: Mapped[Optional[str]] = mapped_column(String(64), comment="交易流水号")
    seller_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="商家业务ID"
    )
    brand_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="品牌业务ID"
    )
    receiver_region_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="收货区县编码"
    )
    channel_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="下单渠道编码"
    )
    order_source: Mapped[Optional[str]] = mapped_column(String(32), comment="下单来源")
    cost_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 2), comment="下单时标准成本金额快照"
    )


class DwdTradeOrderStatusEventDi(Base):
    __tablename__ = "dwd_trade_order_status_event_di"
    __table_args__ = (
        CheckConstraint(
            "(`event_seq_no` > 0)", name="dwd_trade_order_status_event_di_chk_1"
        ),
        CheckConstraint(
            "(`is_terminal_status` in (0,1))",
            name="dwd_trade_order_status_event_di_chk_2",
        ),
        Index("idx_order_status_date", "biz_date", "after_order_status"),
        Index("idx_order_status_order_time", "order_id", "event_time"),
        Index("uk_order_status_seq", "order_id", "event_seq_no", unique=True),
        Index(
            "uk_order_status_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "交易域订单状态迁移事件事实"},
    )

    order_status_event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="订单状态事件业务ID"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    event_seq_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="订单内事件序号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="事件时点用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="事件时点店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    after_order_status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="变更后订单状态"
    )
    status_event_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="状态事件类型"
    )
    is_terminal_status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否终态:0否 1是",
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="状态变更时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取状态变更日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    before_order_status: Mapped[Optional[str]] = mapped_column(
        String(32), comment="变更前订单状态"
    )
    status_reason_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="状态原因编码"
    )
    status_reason_description: Mapped[Optional[str]] = mapped_column(
        String(512), comment="状态原因说明"
    )
    cancel_stage: Mapped[Optional[str]] = mapped_column(String(32), comment="取消阶段")
    operator_id: Mapped[Optional[str]] = mapped_column(
        String(64), comment="操作人业务ID"
    )
    operator_type: Mapped[Optional[str]] = mapped_column(
        String(32), comment="操作人类型"
    )


class DwdTradePayDetailDi(Base):
    __tablename__ = "dwd_trade_pay_detail_di"
    __table_args__ = (
        CheckConstraint(
            "((`installment_count` is null) or (`installment_count` > 0))",
            name="dwd_trade_pay_detail_di_chk_4",
        ),
        CheckConstraint("(`pay_attempt_no` > 0)", name="dwd_trade_pay_detail_di_chk_1"),
        CheckConstraint(
            "(`payment_fee_amount` >= 0)", name="dwd_trade_pay_detail_di_chk_3"
        ),
        CheckConstraint(
            "(`requested_pay_amount` > 0)", name="dwd_trade_pay_detail_di_chk_2"
        ),
        Index("idx_pay_type_date", "payment_type_sk", "biz_date"),
        Index("idx_pay_user_date", "user_sk", "biz_date"),
        Index("uk_pay_attempt", "pay_order_no", "pay_attempt_no", unique=True),
        Index(
            "uk_pay_source_record",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "支付域支付尝试事务事实"},
    )

    pay_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="支付尝试业务ID"
    )
    pay_order_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="支付单号"
    )
    pay_attempt_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="支付单内尝试序号"
    )
    pay_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="支付请求日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="支付请求时用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    payment_type_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="支付方式代理键"
    )
    payment_type_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="支付方式业务编码"
    )
    channel_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="支付渠道代理键",
    )
    pay_scene: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="支付场景"
    )
    requested_pay_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2), nullable=False, comment="本次请求支付金额"
    )
    payment_fee_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="支付手续费金额",
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    pay_request_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="支付请求时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取支付请求日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    channel_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="支付渠道编码"
    )
    installment_count: Mapped[Optional[int]] = mapped_column(
        INTEGER(unsigned=True), comment="分期期数"
    )


class DwdTradePayOrderDetailDi(Base):
    __tablename__ = "dwd_trade_pay_order_detail_di"
    __table_args__ = (
        CheckConstraint(
            "(`allocated_pay_amount` > 0)", name="dwd_trade_pay_order_detail_di_chk_1"
        ),
        Index("idx_pay_allocation_order", "order_id", "order_detail_id"),
        Index("idx_pay_allocation_shop_date", "shop_sk", "biz_date"),
        Index(
            "uk_pay_allocation_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        Index("uk_pay_order_detail", "pay_detail_id", "order_detail_id", unique=True),
        {"comment": "支付域支付到订单明细分摊事实"},
    )

    pay_order_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="支付分摊业务ID"
    )
    pay_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="支付尝试业务ID"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    order_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单明细业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="支付时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    seller_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="支付时商家版本代理键",
    )
    allocated_pay_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2), nullable=False, comment="支付分摊金额"
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    pay_request_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="支付请求时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取支付请求日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    seller_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="商家业务ID"
    )


class DwdTradePayStatusEventDi(Base):
    __tablename__ = "dwd_trade_pay_status_event_di"
    __table_args__ = (
        CheckConstraint(
            "(`event_seq_no` > 0)", name="dwd_trade_pay_status_event_di_chk_1"
        ),
        Index("idx_pay_status_date", "biz_date", "after_pay_status"),
        Index("idx_pay_status_time", "pay_detail_id", "event_time"),
        Index("idx_third_party_pay_no", "third_party_pay_no"),
        Index("uk_pay_status_seq", "pay_detail_id", "event_seq_no", unique=True),
        Index(
            "uk_pay_status_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "支付域支付状态迁移事件事实"},
    )

    pay_status_event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="支付状态事件业务ID"
    )
    pay_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="支付尝试业务ID"
    )
    pay_order_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="支付单号"
    )
    event_seq_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="支付尝试内事件序号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    after_pay_status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="变更后支付状态"
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="状态变更时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取状态变更日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    third_party_pay_no: Mapped[Optional[str]] = mapped_column(
        String(128), comment="第三方支付流水号"
    )
    before_pay_status: Mapped[Optional[str]] = mapped_column(
        String(32), comment="变更前支付状态"
    )
    status_reason_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="状态原因编码"
    )
    status_reason_description: Mapped[Optional[str]] = mapped_column(
        String(512), comment="状态原因说明"
    )


class DwdTradeRefundDetailDi(Base):
    __tablename__ = "dwd_trade_refund_detail_di"
    __table_args__ = (
        CheckConstraint(
            "(`apply_freight_amount` >= 0)", name="dwd_trade_refund_detail_di_chk_5"
        ),
        CheckConstraint(
            "(`apply_goods_amount` >= 0)", name="dwd_trade_refund_detail_di_chk_4"
        ),
        CheckConstraint(
            "(`apply_tax_amount` >= 0)", name="dwd_trade_refund_detail_di_chk_6"
        ),
        CheckConstraint(
            "(`is_quality_issue` in (0,1))", name="dwd_trade_refund_detail_di_chk_2"
        ),
        CheckConstraint(
            "(`need_return_goods` in (0,1))", name="dwd_trade_refund_detail_di_chk_3"
        ),
        CheckConstraint(
            "(`refund_apply_amount` = ((`apply_goods_amount` + `apply_freight_amount`) + `apply_tax_amount`))",
            name="dwd_trade_refund_detail_di_chk_8",
        ),
        CheckConstraint(
            "(`refund_apply_amount` > 0)", name="dwd_trade_refund_detail_di_chk_7"
        ),
        CheckConstraint(
            "(`refund_sku_qty` > 0)", name="dwd_trade_refund_detail_di_chk_1"
        ),
        Index("idx_refund_no", "refund_no"),
        Index("idx_refund_order_detail", "order_id", "order_detail_id"),
        Index("idx_refund_shop_date", "shop_sk", "biz_date"),
        Index("idx_refund_user_date", "user_sk", "biz_date"),
        Index(
            "uk_refund_detail_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "退款域退款申请商品明细事实"},
    )

    refund_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="退款明细业务ID"
    )
    refund_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="退款单号"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    order_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单明细业务ID"
    )
    apply_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="退款申请日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="申请时用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="申请时店铺版本代理键"
    )
    shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="店铺业务ID"
    )
    seller_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="申请时商家版本代理键",
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="申请时SKU版本代理键"
    )
    sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="SKU业务ID"
    )
    refund_sku_qty: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="申请退款商品件数"
    )
    refund_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="退款类型"
    )
    is_quality_issue: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否质量问题:0否 1是",
    )
    need_return_goods: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否需要退货:0否 1是",
    )
    apply_goods_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="申请退商品金额",
    )
    apply_freight_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="申请退运费金额",
    )
    apply_tax_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="申请退税金额",
    )
    refund_apply_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2), nullable=False, comment="申请退款总金额"
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    apply_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="退款申请时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取退款申请日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    seller_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="商家业务ID"
    )
    refund_reason_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="退款原因编码"
    )
    refund_reason_description: Mapped[Optional[str]] = mapped_column(
        String(256), comment="退款原因说明"
    )


class DwdTradeRefundPayDetailDi(Base):
    __tablename__ = "dwd_trade_refund_pay_detail_di"
    __table_args__ = (
        CheckConstraint(
            "(`refund_amount` = ((`refund_goods_amount` + `refund_freight_amount`) + `refund_tax_amount`))",
            name="dwd_trade_refund_pay_detail_di_chk_6",
        ),
        CheckConstraint(
            "(`refund_amount` > 0)", name="dwd_trade_refund_pay_detail_di_chk_5"
        ),
        CheckConstraint(
            "(`refund_freight_amount` >= 0)",
            name="dwd_trade_refund_pay_detail_di_chk_3",
        ),
        CheckConstraint(
            "(`refund_goods_amount` >= 0)", name="dwd_trade_refund_pay_detail_di_chk_2"
        ),
        CheckConstraint(
            "(`refund_pay_attempt_no` > 0)", name="dwd_trade_refund_pay_detail_di_chk_1"
        ),
        CheckConstraint(
            "(`refund_tax_amount` >= 0)", name="dwd_trade_refund_pay_detail_di_chk_4"
        ),
        Index("idx_refund_pay_no", "refund_no"),
        Index("idx_refund_pay_original", "original_pay_detail_id"),
        Index("idx_refund_pay_user_date", "user_sk", "biz_date"),
        Index(
            "uk_refund_pay_attempt",
            "refund_detail_id",
            "refund_pay_attempt_no",
            unique=True,
        ),
        Index(
            "uk_refund_pay_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "退款域退款打款尝试事务事实"},
    )

    refund_pay_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="退款打款尝试业务ID"
    )
    refund_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="退款单号"
    )
    refund_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="退款明细业务ID"
    )
    refund_pay_attempt_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="退款明细内打款尝试序号"
    )
    order_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单业务ID"
    )
    order_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="订单明细业务ID"
    )
    request_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="退款打款请求日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="打款请求时用户版本代理键"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="用户业务ID"
    )
    payment_type_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="原支付方式代理键"
    )
    payment_type_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="原支付方式业务编码"
    )
    channel_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="退款渠道代理键",
    )
    refund_goods_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="退商品金额",
    )
    refund_freight_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="退运费金额",
    )
    refund_tax_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2),
        nullable=False,
        server_default=text("'0.00'"),
        comment="退税金额",
    )
    refund_amount: Mapped[decimal.Decimal] = mapped_column(
        DECIMAL(18, 2), nullable=False, comment="退款打款总金额"
    )
    refund_account_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="退款账户类型"
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'CNY'"), comment="币种编码"
    )
    refund_pay_request_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="退款打款请求时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取退款打款请求日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    original_pay_detail_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="原支付尝试业务ID"
    )
    channel_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="退款渠道编码"
    )


class DwdTradeRefundPayStatusEventDi(Base):
    __tablename__ = "dwd_trade_refund_pay_status_event_di"
    __table_args__ = (
        CheckConstraint(
            "(`event_seq_no` > 0)", name="dwd_trade_refund_pay_status_event_di_chk_1"
        ),
        Index("idx_refund_pay_status_date", "biz_date", "after_refund_pay_status"),
        Index("idx_refund_pay_status_time", "refund_pay_detail_id", "event_time"),
        Index("idx_third_party_refund_no", "third_party_refund_no"),
        Index(
            "uk_refund_pay_status_seq",
            "refund_pay_detail_id",
            "event_seq_no",
            unique=True,
        ),
        Index(
            "uk_refund_pay_status_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "退款域退款打款状态迁移事件事实"},
    )

    refund_pay_status_event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="退款打款状态事件业务ID"
    )
    refund_pay_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="退款打款尝试业务ID"
    )
    event_seq_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="打款尝试内事件序号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    after_refund_pay_status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="变更后打款状态"
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="状态变更时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取状态变更日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    third_party_refund_no: Mapped[Optional[str]] = mapped_column(
        String(128), comment="第三方退款流水号"
    )
    before_refund_pay_status: Mapped[Optional[str]] = mapped_column(
        String(32), comment="变更前打款状态"
    )
    status_reason_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="状态原因编码"
    )
    status_reason_description: Mapped[Optional[str]] = mapped_column(
        String(512), comment="状态原因说明"
    )


class DwdTradeRefundStatusEventDi(Base):
    __tablename__ = "dwd_trade_refund_status_event_di"
    __table_args__ = (
        CheckConstraint(
            "((`approved_amount_delta` is null) or (`approved_amount_delta` >= 0))",
            name="dwd_trade_refund_status_event_di_chk_2",
        ),
        CheckConstraint(
            "(`event_seq_no` > 0)", name="dwd_trade_refund_status_event_di_chk_1"
        ),
        Index("idx_refund_status_date", "biz_date", "after_refund_status"),
        Index("idx_refund_status_time", "refund_detail_id", "event_time"),
        Index("uk_refund_status_seq", "refund_detail_id", "event_seq_no", unique=True),
        Index(
            "uk_refund_status_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "退款域退款状态迁移事件事实"},
    )

    refund_status_event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="退款状态事件业务ID"
    )
    refund_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="退款明细业务ID"
    )
    refund_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="退款单号"
    )
    event_seq_no: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="退款明细内事件序号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    after_refund_status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="变更后退款状态"
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="状态变更时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取状态变更日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    before_refund_status: Mapped[Optional[str]] = mapped_column(
        String(32), comment="变更前退款状态"
    )
    approved_amount_delta: Mapped[Optional[decimal.Decimal]] = mapped_column(
        DECIMAL(18, 2), comment="本事件新确认的审核通过金额"
    )
    status_reason_code: Mapped[Optional[str]] = mapped_column(
        String(32), comment="状态原因编码"
    )
    status_reason_description: Mapped[Optional[str]] = mapped_column(
        String(512), comment="状态原因说明"
    )
    operator_id: Mapped[Optional[str]] = mapped_column(
        String(64), comment="操作人业务ID"
    )
    operator_type: Mapped[Optional[str]] = mapped_column(
        String(32), comment="操作人类型"
    )


class DwdTrafficPageViewDi(Base):
    __tablename__ = "dwd_traffic_page_view_di"
    __table_args__ = (
        Index("idx_page_view_page_date", "page_sk", "biz_date"),
        Index("idx_page_view_promotion_date", "promotion_version_sk", "biz_date"),
        Index("idx_page_view_search", "search_detail_id"),
        Index("idx_page_view_session_time", "session_id", "event_time"),
        Index("idx_page_view_sku_date", "sku_sk", "biz_date"),
        Index("idx_page_view_user_date", "user_sk", "biz_date"),
        Index("uk_page_view_event_no", "event_no", unique=True),
        Index(
            "uk_page_view_source", "source_system_code", "source_record_id", unique=True
        ),
        {"comment": "流量域页面访问事件事实"},
    )

    page_view_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="页面访问事件业务ID"
    )
    event_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="事件流水号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="事件时点用户版本代理键",
    )
    device_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="设备ID"
    )
    session_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="会话ID"
    )
    page_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="页面代理键"
    )
    page_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="页面业务ID"
    )
    last_page_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="上一个页面代理键",
    )
    channel_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("'-1'"), comment="渠道代理键"
    )
    shop_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="关联店铺版本代理键",
    )
    sku_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="关联SKU版本代理键",
    )
    spu_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="关联SPU版本代理键",
    )
    category_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="关联类目版本代理键",
    )
    promotion_version_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="关联促销规则版本代理键",
    )
    region_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="访问区域版本代理键",
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="页面加载时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取页面加载日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="用户业务ID，游客为空"
    )
    last_page_id: Mapped[Optional[str]] = mapped_column(
        String(64), comment="上一个页面业务ID"
    )
    channel_code: Mapped[Optional[str]] = mapped_column(String(32), comment="渠道编码")
    shop_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="关联店铺业务ID"
    )
    sku_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="关联SKU业务ID"
    )
    spu_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="关联SPU业务ID"
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="关联类目业务ID"
    )
    promotion_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="关联活动业务ID"
    )
    search_detail_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="来源搜索请求业务ID"
    )
    business_type: Mapped[Optional[str]] = mapped_column(
        String(32), comment="其他关联业务对象类型"
    )
    business_id: Mapped[Optional[str]] = mapped_column(
        String(64), comment="其他关联业务对象ID"
    )
    client_type: Mapped[Optional[str]] = mapped_column(String(32), comment="客户端类型")
    app_version: Mapped[Optional[str]] = mapped_column(String(32), comment="应用版本")
    os_type: Mapped[Optional[str]] = mapped_column(String(32), comment="操作系统")
    region_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="访问区域编码"
    )
    stay_duration_sec: Mapped[Optional[int]] = mapped_column(
        INTEGER(unsigned=True), comment="页面停留秒数"
    )


class DwdTrafficSearchClickDi(Base):
    __tablename__ = "dwd_traffic_search_click_di"
    __table_args__ = (
        CheckConstraint("(`click_rank` > 0)", name="dwd_traffic_search_click_di_chk_1"),
        Index("idx_search_click_request_time", "search_detail_id", "event_time"),
        Index("idx_search_click_sku_date", "click_sku_sk", "biz_date"),
        Index("idx_search_click_user_date", "user_sk", "biz_date"),
        Index("uk_search_click_event_no", "event_no", unique=True),
        Index(
            "uk_search_click_source",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "流量域搜索结果点击事件事实"},
    )

    search_click_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="搜索点击事件业务ID"
    )
    search_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="搜索请求业务ID"
    )
    event_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="点击事件流水号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="点击日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="点击时用户版本代理键",
    )
    device_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="设备ID"
    )
    session_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="会话ID"
    )
    channel_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("'-1'"), comment="渠道代理键"
    )
    click_sku_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="点击时SKU版本代理键"
    )
    click_sku_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="点击SKU业务ID"
    )
    click_spu_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="点击时SPU版本代理键"
    )
    click_spu_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="点击SPU业务ID"
    )
    click_shop_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="点击时店铺版本代理键"
    )
    click_shop_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="点击店铺业务ID"
    )
    click_category_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="点击时类目版本代理键"
    )
    click_category_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, comment="点击类目业务ID"
    )
    click_rank: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="点击结果位次"
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="点击时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取点击日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="用户业务ID，游客为空"
    )
    channel_code: Mapped[Optional[str]] = mapped_column(String(32), comment="渠道编码")


class DwdTrafficSearchDi(Base):
    __tablename__ = "dwd_traffic_search_di"
    __table_args__ = (
        CheckConstraint(
            "((`is_no_result` = 0) or (`result_total_count` = 0))",
            name="dwd_traffic_search_di_chk_3",
        ),
        CheckConstraint(
            "(`is_no_result` in (0,1))", name="dwd_traffic_search_di_chk_1"
        ),
        CheckConstraint(
            "(`is_search_success` in (0,1))", name="dwd_traffic_search_di_chk_2"
        ),
        Index("idx_search_keyword_date", "normalized_keyword", "biz_date"),
        Index("idx_search_session_time", "session_id", "event_time"),
        Index("idx_search_user_date", "user_sk", "biz_date"),
        Index("uk_search_event_no", "event_no", unique=True),
        Index(
            "uk_search_source_record",
            "source_system_code",
            "source_record_id",
            unique=True,
        ),
        {"comment": "流量域搜索请求事件事实"},
    )

    search_detail_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="搜索请求业务ID"
    )
    event_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="事件流水号"
    )
    event_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="事件日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="事件时点用户版本代理键",
    )
    device_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="设备ID"
    )
    session_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="会话ID"
    )
    channel_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("'-1'"), comment="渠道代理键"
    )
    search_keyword: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="搜索词"
    )
    result_total_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="搜索结果总数",
    )
    is_no_result: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否无结果:0否 1是",
    )
    is_search_success: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'1'"),
        comment="请求是否成功:0否 1是",
    )
    event_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="搜索请求时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取搜索请求日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源事件唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="用户业务ID，游客为空"
    )
    channel_code: Mapped[Optional[str]] = mapped_column(String(32), comment="渠道编码")
    normalized_keyword: Mapped[Optional[str]] = mapped_column(
        String(256), comment="归一化搜索词"
    )
    search_source: Mapped[Optional[str]] = mapped_column(String(32), comment="搜索入口")


class DwdTrafficSessionDi(Base):
    __tablename__ = "dwd_traffic_session_di"
    __table_args__ = (
        CheckConstraint(
            "((`is_bounce` = 0) or (`page_view_count` <= 1))",
            name="dwd_traffic_session_di_chk_3",
        ),
        CheckConstraint("(`is_bounce` in (0,1))", name="dwd_traffic_session_di_chk_2"),
        CheckConstraint(
            "(`session_start_time` <= `session_end_time`)",
            name="dwd_traffic_session_di_chk_1",
        ),
        Index("idx_session_channel_date", "channel_sk", "biz_date"),
        Index("idx_session_start_time", "session_start_time"),
        Index("idx_session_user_date", "user_sk", "biz_date"),
        Index("uk_session_id", "session_id", unique=True),
        Index(
            "uk_session_source", "source_system_code", "source_record_id", unique=True
        ),
        {"comment": "流量域客户端会话事实"},
    )

    session_fact_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, comment="会话事实业务ID"
    )
    session_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="会话ID"
    )
    session_date_key: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, comment="会话开始日期键"
    )
    user_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="会话开始时用户版本代理键",
    )
    device_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="设备ID"
    )
    channel_sk: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("'-1'"), comment="渠道代理键"
    )
    entry_page_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="入口页面代理键",
    )
    exit_page_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="退出页面代理键",
    )
    region_sk: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("'-1'"),
        comment="会话区域版本代理键",
    )
    page_view_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="页面访问次数",
    )
    search_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="搜索次数",
    )
    session_duration_sec: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="会话持续秒数",
    )
    is_bounce: Mapped[int] = mapped_column(
        TINYINT(unsigned=True),
        nullable=False,
        server_default=text("'0'"),
        comment="是否跳出会话:0否 1是",
    )
    session_start_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="会话开始时间"
    )
    session_end_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, comment="会话结束时间"
    )
    biz_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="业务日期，取会话开始日期"
    )
    source_system_code: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源系统编码"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="源记录唯一标识"
    )
    load_batch_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="装载批次ID"
    )
    dw_load_time: Mapped[datetime.datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        comment="入仓时间",
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True), comment="用户业务ID，游客为空"
    )
    channel_code: Mapped[Optional[str]] = mapped_column(String(32), comment="渠道编码")
    entry_page_id: Mapped[Optional[str]] = mapped_column(
        String(64), comment="入口页面业务ID"
    )
    exit_page_id: Mapped[Optional[str]] = mapped_column(
        String(64), comment="退出页面业务ID"
    )
    region_code: Mapped[Optional[str]] = mapped_column(
        String(20), comment="会话区域编码"
    )
    client_type: Mapped[Optional[str]] = mapped_column(String(32), comment="客户端类型")
    app_version: Mapped[Optional[str]] = mapped_column(String(32), comment="应用版本")
    os_type: Mapped[Optional[str]] = mapped_column(String(32), comment="操作系统")
    ip_masked: Mapped[Optional[str]] = mapped_column(String(64), comment="访问IP脱敏值")
