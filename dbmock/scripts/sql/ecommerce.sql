-- 电商数仓一致性维度与原子事实建表脚本
-- 适用数据库为 MySQL 8.0 及以上版本
-- 1) _zip 表示 SCD2 拉链维度，生效区间统一采用左闭右开语义
-- 2) 无 _zip 后缀的普通维度采用 Type 1 策略并按业务键原地更新
-- 3) _version 表示不可变业务规则版本，不使用通用拉链当前态语义
-- 4) _di 表示按业务日期组织的增量事实，_df 表示每日周期快照事实
-- 5) 事实表同时保留事件时点代理键和源系统业务键
-- 6) -1 约定为未知维度代理键，装载任务应预置未知维度成员
-- 7) 状态变化只写事件事实，不覆盖原子交易事实
-- 8) biz_date 表示业务发生日期，dw_load_time 表示实际入仓时间
-- 9) 金额默认使用人民币元，所有金额口径必须通过指标字典统一解释
-- 10) 数仓不声明物理外键，引用完整性由装载任务和数据质量规则保证

/* =========================
   DIM 一致性维度
   ========================= */

CREATE TABLE dim_date (
    date_key INT UNSIGNED NOT NULL COMMENT '日期键，格式YYYYMMDD',
    full_date DATE NOT NULL COMMENT '自然日期',
    calendar_year SMALLINT UNSIGNED NOT NULL COMMENT '自然年',
    calendar_quarter TINYINT UNSIGNED NOT NULL COMMENT '自然季度',
    calendar_month TINYINT UNSIGNED NOT NULL COMMENT '自然月',
    year_month_code CHAR(7) NOT NULL COMMENT '年月，格式YYYY-MM',
    week_of_year TINYINT UNSIGNED NOT NULL COMMENT '年内周序号',
    day_of_month TINYINT UNSIGNED NOT NULL COMMENT '月内日序号',
    day_of_week TINYINT UNSIGNED NOT NULL COMMENT '周内日序号，1表示周一',
    day_name_cn VARCHAR(8) NOT NULL COMMENT '中文星期名称',
    is_weekend TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否周末:0否 1是',
    is_holiday TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否法定节假日:0否 1是',
    is_workday TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否工作日:0否 1是',
    holiday_name VARCHAR(64) DEFAULT NULL COMMENT '节假日名称',
    fiscal_year SMALLINT UNSIGNED NOT NULL COMMENT '财年',
    fiscal_quarter TINYINT UNSIGNED NOT NULL COMMENT '财年季度',
    PRIMARY KEY (date_key),
    UNIQUE KEY uk_full_date (full_date),
    CHECK (
        date_key = YEAR(full_date) * 10000
        + MONTH(full_date) * 100
        + DAY(full_date)
    ),
    CHECK (calendar_year = YEAR(full_date)),
    CHECK (calendar_quarter BETWEEN 1 AND 4),
    CHECK (calendar_month BETWEEN 1 AND 12),
    CHECK (week_of_year BETWEEN 1 AND 53),
    CHECK (day_of_month BETWEEN 1 AND 31),
    CHECK (day_of_week BETWEEN 1 AND 7),
    CHECK (fiscal_quarter BETWEEN 1 AND 4),
    CHECK (is_weekend IN (0, 1)),
    CHECK (is_holiday IN (0, 1)),
    CHECK (is_workday IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '公共日期维度';

CREATE TABLE dim_channel_info (
    channel_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '渠道维度代理键',
    channel_code VARCHAR(32) NOT NULL COMMENT '渠道业务编码',
    channel_name VARCHAR(64) NOT NULL COMMENT '渠道名称',
    channel_group VARCHAR(32) DEFAULT NULL COMMENT '渠道分组',
    platform_type VARCHAR(32) DEFAULT NULL COMMENT '平台类型',
    traffic_source_type VARCHAR(32) DEFAULT NULL COMMENT '流量来源类型',
    channel_status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '状态:0停用 1启用',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    PRIMARY KEY (channel_sk),
    UNIQUE KEY uk_channel_code (channel_code),
    CHECK (channel_status IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '渠道Type 1一致性维度';

CREATE TABLE dim_page_info (
    page_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '页面维度代理键',
    page_id VARCHAR(64) NOT NULL COMMENT '页面业务ID',
    page_name VARCHAR(128) NOT NULL COMMENT '页面名称',
    page_type VARCHAR(32) NOT NULL COMMENT '页面类型',
    business_domain VARCHAR(32) DEFAULT NULL COMMENT '所属业务域',
    page_path_pattern VARCHAR(512) DEFAULT NULL COMMENT '页面路径模板',
    page_status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '状态:0停用 1启用',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    PRIMARY KEY (page_sk),
    UNIQUE KEY uk_page_id (page_id),
    KEY idx_page_type (page_type),
    CHECK (page_status IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '页面Type 1一致性维度';

CREATE TABLE dim_geo_region_zip (
    region_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '行政区域维度代理键',
    region_code VARCHAR(20) NOT NULL COMMENT '区域业务编码',
    region_name VARCHAR(128) NOT NULL COMMENT '区域名称',
    region_level TINYINT UNSIGNED NOT NULL COMMENT '区域级别:1国家 2省 3市 4区县 5街道',
    parent_region_code VARCHAR(20) DEFAULT NULL COMMENT '父级区域编码',
    country_code VARCHAR(20) DEFAULT NULL COMMENT '国家编码',
    country_name VARCHAR(128) DEFAULT NULL COMMENT '国家名称',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '省编码',
    province_name VARCHAR(128) DEFAULT NULL COMMENT '省名称',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '市编码',
    city_name VARCHAR(128) DEFAULT NULL COMMENT '市名称',
    district_code VARCHAR(20) DEFAULT NULL COMMENT '区县编码',
    district_name VARCHAR(128) DEFAULT NULL COMMENT '区县名称',
    region_path VARCHAR(512) DEFAULT NULL COMMENT '完整区域路径',
    zip_code VARCHAR(16) DEFAULT NULL COMMENT '邮编',
    region_status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '状态:0停用 1启用',
    effective_start_time DATETIME(6) NOT NULL COMMENT '版本生效时间',
    effective_end_time DATETIME(6) NOT NULL COMMENT '版本失效时间',
    version_no INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '版本号',
    is_current TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    current_region_code VARCHAR(20) GENERATED ALWAYS AS (
        CASE WHEN is_current = 1 THEN region_code END
    ) STORED,
    PRIMARY KEY (region_sk),
    UNIQUE KEY uk_region_start (region_code, effective_start_time),
    UNIQUE KEY uk_region_current (current_region_code),
    KEY idx_region_effective (
        region_code, effective_start_time, effective_end_time
    ),
    KEY idx_parent_region (parent_region_code),
    KEY idx_region_hierarchy (province_code, city_code, district_code),
    CHECK (region_level BETWEEN 1 AND 5),
    CHECK (effective_start_time < effective_end_time),
    CHECK (region_status IN (0, 1)),
    CHECK (is_current IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '行政区域一致性维度拉链表';

CREATE TABLE dim_user_info_zip (
    user_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '用户维度代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    user_name VARCHAR(64) DEFAULT NULL COMMENT '用户名',
    nick_name VARCHAR(64) DEFAULT NULL COMMENT '昵称',
    gender VARCHAR(8) NOT NULL DEFAULT '未知' COMMENT '性别:未知/男/女',
    birthday DATE DEFAULT NULL COMMENT '生日',
    phone VARCHAR(20) DEFAULT NULL COMMENT '手机号脱敏值',
    email VARCHAR(128) DEFAULT NULL COMMENT '邮箱脱敏值',
    register_time DATETIME(6) DEFAULT NULL COMMENT '注册时间',
    register_channel_code VARCHAR(32) DEFAULT NULL COMMENT '注册渠道编码',
    register_source VARCHAR(32) DEFAULT NULL COMMENT '注册来源',
    user_level VARCHAR(16) NOT NULL DEFAULT '1' COMMENT '会员等级',
    is_vip TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否VIP:0否 1是',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '常驻省编码',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '常驻市编码',
    district_code VARCHAR(20) DEFAULT NULL COMMENT '常驻区编码',
    occupation VARCHAR(64) DEFAULT NULL COMMENT '职业',
    income_level VARCHAR(32) DEFAULT NULL COMMENT '收入等级',
    education_level VARCHAR(32) DEFAULT NULL COMMENT '学历等级',
    marital_status VARCHAR(16) DEFAULT NULL COMMENT '婚姻状态',
    user_status VARCHAR(16) NOT NULL DEFAULT '正常' COMMENT '用户状态',
    effective_start_time DATETIME(6) NOT NULL COMMENT '版本生效时间',
    effective_end_time DATETIME(6) NOT NULL COMMENT '版本失效时间',
    version_no INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '版本号',
    is_current TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    current_user_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_current = 1 THEN user_id END
    ) STORED,
    PRIMARY KEY (user_sk),
    UNIQUE KEY uk_user_start (user_id, effective_start_time),
    UNIQUE KEY uk_user_current (current_user_id),
    KEY idx_user_effective (user_id, effective_start_time, effective_end_time),
    KEY idx_user_region (province_code, city_code, district_code),
    KEY idx_user_register_time (register_time),
    CHECK (effective_start_time < effective_end_time),
    CHECK (is_vip IN (0, 1)),
    CHECK (is_current IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '用户一致性维度拉链表';

CREATE TABLE dim_user_tag_info (
    user_tag_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '用户标签代理键',
    tag_code VARCHAR(64) NOT NULL COMMENT '标签编码',
    tag_name VARCHAR(128) NOT NULL COMMENT '标签名称',
    tag_group VARCHAR(64) DEFAULT NULL COMMENT '标签分组',
    tag_value_type VARCHAR(16) NOT NULL DEFAULT 'BOOLEAN' COMMENT '标签值类型',
    tag_description VARCHAR(512) DEFAULT NULL COMMENT '标签说明',
    tag_status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '状态:0停用 1启用',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    PRIMARY KEY (user_tag_sk),
    UNIQUE KEY uk_tag_code (tag_code),
    CHECK (tag_status IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '用户标签维度';

CREATE TABLE bridge_user_tag_relation_zip (
    user_tag_relation_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '用户标签关系代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    user_tag_sk BIGINT NOT NULL COMMENT '用户标签代理键',
    tag_value VARCHAR(256) DEFAULT NULL COMMENT '标签值',
    tag_score DECIMAL(10, 6) DEFAULT NULL COMMENT '标签置信度或权重',
    effective_start_time DATETIME(6) NOT NULL COMMENT '关系生效时间',
    effective_end_time DATETIME(6) NOT NULL COMMENT '关系失效时间',
    is_current TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否当前关系:0否 1是',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (user_tag_relation_sk),
    UNIQUE KEY uk_user_tag_start (user_id, user_tag_sk, effective_start_time),
    KEY idx_user_tag_current (user_id, user_tag_sk, is_current),
    CHECK (effective_start_time < effective_end_time),
    CHECK (is_current IN (0, 1)),
    CHECK (tag_score IS NULL OR tag_score BETWEEN 0 AND 1)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '用户与标签多值关系拉链桥表';

CREATE TABLE dim_seller_info_zip (
    seller_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '商家维度代理键',
    seller_id BIGINT UNSIGNED NOT NULL COMMENT '商家业务ID',
    seller_name VARCHAR(128) NOT NULL COMMENT '商家名称',
    seller_type VARCHAR(32) DEFAULT NULL COMMENT '商家类型',
    industry_type VARCHAR(64) DEFAULT NULL COMMENT '所属行业',
    country_code VARCHAR(20) DEFAULT NULL COMMENT '注册国家编码',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '注册省编码',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '注册市编码',
    settle_date DATE DEFAULT NULL COMMENT '入驻日期',
    seller_status VARCHAR(16) NOT NULL DEFAULT '正常' COMMENT '商家状态',
    effective_start_time DATETIME(6) NOT NULL COMMENT '版本生效时间',
    effective_end_time DATETIME(6) NOT NULL COMMENT '版本失效时间',
    version_no INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '版本号',
    is_current TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    current_seller_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_current = 1 THEN seller_id END
    ) STORED,
    PRIMARY KEY (seller_sk),
    UNIQUE KEY uk_seller_start (seller_id, effective_start_time),
    UNIQUE KEY uk_seller_current (current_seller_id),
    KEY idx_seller_effective (
        seller_id, effective_start_time, effective_end_time
    ),
    CHECK (effective_start_time < effective_end_time),
    CHECK (is_current IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '商家一致性维度拉链表';

CREATE TABLE dim_shop_info_zip (
    shop_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '店铺维度代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    shop_name VARCHAR(128) NOT NULL COMMENT '店铺名称',
    shop_type VARCHAR(32) NOT NULL DEFAULT '普通店' COMMENT '店铺类型',
    seller_id BIGINT UNSIGNED NOT NULL COMMENT '商家业务ID',
    industry_type VARCHAR(64) DEFAULT NULL COMMENT '行业类型',
    service_score DECIMAL(4, 2) DEFAULT NULL COMMENT '服务评分',
    logistics_score DECIMAL(4, 2) DEFAULT NULL COMMENT '物流评分',
    description_score DECIMAL(4, 2) DEFAULT NULL COMMENT '描述评分',
    open_time DATETIME(6) DEFAULT NULL COMMENT '开店时间',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '店铺省编码',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '店铺市编码',
    district_code VARCHAR(20) DEFAULT NULL COMMENT '店铺区编码',
    is_self_operated TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否自营:0否 1是',
    is_cross_border TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否跨境:0否 1是',
    shop_status VARCHAR(16) NOT NULL DEFAULT '营业' COMMENT '店铺状态',
    effective_start_time DATETIME(6) NOT NULL COMMENT '版本生效时间',
    effective_end_time DATETIME(6) NOT NULL COMMENT '版本失效时间',
    version_no INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '版本号',
    is_current TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    current_shop_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_current = 1 THEN shop_id END
    ) STORED,
    PRIMARY KEY (shop_sk),
    UNIQUE KEY uk_shop_start (shop_id, effective_start_time),
    UNIQUE KEY uk_shop_current (current_shop_id),
    KEY idx_shop_effective (shop_id, effective_start_time, effective_end_time),
    KEY idx_shop_seller (seller_id),
    KEY idx_shop_region (province_code, city_code, district_code),
    CHECK (effective_start_time < effective_end_time),
    CHECK (is_self_operated IN (0, 1)),
    CHECK (is_cross_border IN (0, 1)),
    CHECK (is_current IN (0, 1)),
    CHECK (is_deleted IN (0, 1)),
    CHECK (service_score IS NULL OR service_score BETWEEN 0 AND 5),
    CHECK (logistics_score IS NULL OR logistics_score BETWEEN 0 AND 5),
    CHECK (description_score IS NULL OR description_score BETWEEN 0 AND 5)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '店铺一致性维度拉链表';

CREATE TABLE dim_category_info_zip (
    category_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '类目维度代理键',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '类目业务ID',
    category_name VARCHAR(128) NOT NULL COMMENT '类目名称',
    category_level TINYINT UNSIGNED NOT NULL COMMENT '类目层级',
    parent_category_id BIGINT UNSIGNED DEFAULT NULL COMMENT '父类目业务ID',
    parent_category_name VARCHAR(128) DEFAULT NULL COMMENT '父类目名称快照',
    root_category_id BIGINT UNSIGNED DEFAULT NULL COMMENT '一级类目业务ID',
    root_category_name VARCHAR(128) DEFAULT NULL COMMENT '一级类目名称快照',
    category_path_ids VARCHAR(512) NOT NULL COMMENT '类目ID完整路径',
    category_path_names VARCHAR(1024) NOT NULL COMMENT '类目名称完整路径',
    is_leaf TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否叶子类目:0否 1是',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序号',
    category_status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '状态:0停用 1启用',
    effective_start_time DATETIME(6) NOT NULL COMMENT '版本生效时间',
    effective_end_time DATETIME(6) NOT NULL COMMENT '版本失效时间',
    version_no INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '版本号',
    is_current TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    current_category_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_current = 1 THEN category_id END
    ) STORED,
    PRIMARY KEY (category_sk),
    UNIQUE KEY uk_category_start (category_id, effective_start_time),
    UNIQUE KEY uk_category_current (current_category_id),
    KEY idx_category_effective (
        category_id, effective_start_time, effective_end_time
    ),
    KEY idx_category_parent (parent_category_id),
    KEY idx_category_root (root_category_id),
    CHECK (category_level BETWEEN 1 AND 10),
    CHECK (effective_start_time < effective_end_time),
    CHECK (is_leaf IN (0, 1)),
    CHECK (category_status IN (0, 1)),
    CHECK (is_current IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '商品类目一致性维度拉链表';

CREATE TABLE dim_brand_info (
    brand_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '品牌维度代理键',
    brand_id BIGINT UNSIGNED NOT NULL COMMENT '品牌业务ID',
    brand_name VARCHAR(128) NOT NULL COMMENT '品牌名称',
    brand_name_en VARCHAR(128) DEFAULT NULL COMMENT '品牌英文名',
    brand_alias VARCHAR(128) DEFAULT NULL COMMENT '品牌别名',
    brand_logo_url VARCHAR(512) DEFAULT NULL COMMENT '品牌Logo地址',
    brand_story VARCHAR(2000) DEFAULT NULL COMMENT '品牌故事',
    country_code VARCHAR(20) DEFAULT NULL COMMENT '品牌国家编码',
    country_name VARCHAR(64) DEFAULT NULL COMMENT '品牌国家名称',
    first_letter CHAR(1) DEFAULT NULL COMMENT '品牌首字母',
    brand_status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '状态:0停用 1启用',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    PRIMARY KEY (brand_sk),
    UNIQUE KEY uk_brand_id (brand_id),
    KEY idx_brand_name (brand_name),
    CHECK (brand_status IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '品牌Type 1一致性维度';

CREATE TABLE dim_payment_type (
    payment_type_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '支付方式维度代理键',
    payment_type_code VARCHAR(32) NOT NULL COMMENT '支付方式业务编码',
    payment_type_name VARCHAR(64) NOT NULL COMMENT '支付方式名称',
    payment_institution_code VARCHAR(32) DEFAULT NULL COMMENT '支付机构编码',
    payment_institution_name VARCHAR(64) DEFAULT NULL COMMENT '支付机构名称',
    is_online TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否线上支付:0否 1是',
    is_installment TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否支持分期:0否 1是',
    payment_type_status TINYINT UNSIGNED NOT NULL DEFAULT 1
    COMMENT '状态:0停用 1启用',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    PRIMARY KEY (payment_type_sk),
    UNIQUE KEY uk_payment_type_code (payment_type_code),
    CHECK (is_online IN (0, 1)),
    CHECK (is_installment IN (0, 1)),
    CHECK (payment_type_status IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '支付方式Type 1一致性维度';

CREATE TABLE dim_logistics_company (
    logistics_company_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '物流公司维度代理键',
    logistics_company_id BIGINT UNSIGNED NOT NULL COMMENT '物流公司业务ID',
    logistics_company_code VARCHAR(32) NOT NULL COMMENT '物流公司编码',
    logistics_company_name VARCHAR(128) NOT NULL COMMENT '物流公司名称',
    logistics_type VARCHAR(32) DEFAULT NULL COMMENT '物流类型',
    service_phone VARCHAR(32) DEFAULT NULL COMMENT '客服电话',
    is_trace_supported TINYINT UNSIGNED NOT NULL DEFAULT 1
    COMMENT '是否支持轨迹查询:0否 1是',
    logistics_company_status TINYINT UNSIGNED NOT NULL DEFAULT 1
    COMMENT '状态:0停用 1启用',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    PRIMARY KEY (logistics_company_sk),
    UNIQUE KEY uk_logistics_company_id (logistics_company_id),
    UNIQUE KEY uk_logistics_company_code (logistics_company_code),
    CHECK (is_trace_supported IN (0, 1)),
    CHECK (logistics_company_status IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '物流公司Type 1一致性维度';

CREATE TABLE dim_warehouse_info_zip (
    warehouse_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '仓库维度代理键',
    warehouse_id BIGINT UNSIGNED NOT NULL COMMENT '仓库业务ID',
    warehouse_code VARCHAR(32) NOT NULL COMMENT '仓库编码',
    warehouse_name VARCHAR(128) NOT NULL COMMENT '仓库名称',
    warehouse_type VARCHAR(32) NOT NULL COMMENT '仓库类型',
    owner_type VARCHAR(32) DEFAULT NULL COMMENT '仓库归属类型',
    owner_id BIGINT UNSIGNED DEFAULT NULL COMMENT '仓库归属方业务ID',
    country_code VARCHAR(20) DEFAULT NULL COMMENT '国家编码',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '省编码',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '市编码',
    district_code VARCHAR(20) DEFAULT NULL COMMENT '区县编码',
    address VARCHAR(512) DEFAULT NULL COMMENT '仓库地址脱敏值',
    warehouse_status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '状态:0停用 1启用',
    effective_start_time DATETIME(6) NOT NULL COMMENT '版本生效时间',
    effective_end_time DATETIME(6) NOT NULL COMMENT '版本失效时间',
    version_no INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '版本号',
    is_current TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    current_warehouse_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_current = 1 THEN warehouse_id END
    ) STORED,
    PRIMARY KEY (warehouse_sk),
    UNIQUE KEY uk_warehouse_start (warehouse_id, effective_start_time),
    UNIQUE KEY uk_warehouse_current (current_warehouse_id),
    UNIQUE KEY uk_warehouse_code_start (warehouse_code, effective_start_time),
    KEY idx_warehouse_effective (
        warehouse_id, effective_start_time, effective_end_time
    ),
    KEY idx_warehouse_region (province_code, city_code, district_code),
    CHECK (effective_start_time < effective_end_time),
    CHECK (warehouse_status IN (0, 1)),
    CHECK (is_current IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '仓库一致性维度拉链表';

CREATE TABLE dim_spu_info_zip (
    spu_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT 'SPU维度代理键',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU业务ID',
    spu_name VARCHAR(256) NOT NULL COMMENT 'SPU名称',
    spu_sub_title VARCHAR(512) DEFAULT NULL COMMENT 'SPU副标题',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '叶子类目业务ID',
    brand_id BIGINT UNSIGNED DEFAULT NULL COMMENT '品牌业务ID',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    is_virtual TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否虚拟商品:0否 1是',
    is_presale TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否预售:0否 1是',
    presale_start_time DATETIME(6) DEFAULT NULL COMMENT '预售开始时间',
    presale_end_time DATETIME(6) DEFAULT NULL COMMENT '预售结束时间',
    weight_kg DECIMAL(16, 3) DEFAULT NULL COMMENT '商品重量千克',
    volume_m3 DECIMAL(16, 6) DEFAULT NULL COMMENT '商品体积立方米',
    on_shelf_time DATETIME(6) DEFAULT NULL COMMENT '上架时间',
    spu_status VARCHAR(16) NOT NULL DEFAULT '在售' COMMENT 'SPU状态',
    effective_start_time DATETIME(6) NOT NULL COMMENT '版本生效时间',
    effective_end_time DATETIME(6) NOT NULL COMMENT '版本失效时间',
    version_no INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '版本号',
    is_current TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    current_spu_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_current = 1 THEN spu_id END
    ) STORED,
    PRIMARY KEY (spu_sk),
    UNIQUE KEY uk_spu_start (spu_id, effective_start_time),
    UNIQUE KEY uk_spu_current (current_spu_id),
    KEY idx_spu_effective (spu_id, effective_start_time, effective_end_time),
    KEY idx_spu_shop_category (shop_id, category_id),
    KEY idx_spu_brand (brand_id),
    CHECK (effective_start_time < effective_end_time),
    CHECK (is_virtual IN (0, 1)),
    CHECK (is_presale IN (0, 1)),
    CHECK (weight_kg IS NULL OR weight_kg >= 0),
    CHECK (volume_m3 IS NULL OR volume_m3 >= 0),
    CHECK (is_current IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'SPU一致性维度拉链表';

CREATE TABLE dim_sku_info_zip (
    sku_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT 'SKU维度代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU业务ID',
    sku_name VARCHAR(256) NOT NULL COMMENT 'SKU名称',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU业务ID',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '叶子类目业务ID',
    brand_id BIGINT UNSIGNED DEFAULT NULL COMMENT '品牌业务ID',
    bar_code VARCHAR(64) DEFAULT NULL COMMENT '商品条码',
    sku_specs_json JSON DEFAULT NULL COMMENT '低频SKU规格属性',
    unit VARCHAR(16) NOT NULL DEFAULT '件' COMMENT '计量单位',
    warning_stock_qty INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '预警库存量',
    is_hot_sale TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否热销:0否 1是',
    is_new TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否新品:0否 1是',
    sku_status VARCHAR(16) NOT NULL DEFAULT '在售' COMMENT 'SKU状态',
    effective_start_time DATETIME(6) NOT NULL COMMENT '版本生效时间',
    effective_end_time DATETIME(6) NOT NULL COMMENT '版本失效时间',
    version_no INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '版本号',
    is_current TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '源记录是否删除:0否 1是',
    attribute_hash CHAR(64) NOT NULL COMMENT '业务属性哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '首次入仓时间',
    dw_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '最近更新时间',
    current_sku_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_current = 1 THEN sku_id END
    ) STORED,
    PRIMARY KEY (sku_sk),
    UNIQUE KEY uk_sku_start (sku_id, effective_start_time),
    UNIQUE KEY uk_sku_current (current_sku_id),
    KEY idx_sku_effective (sku_id, effective_start_time, effective_end_time),
    KEY idx_sku_spu (spu_id),
    KEY idx_sku_shop_category (shop_id, category_id),
    KEY idx_sku_brand (brand_id),
    CHECK (effective_start_time < effective_end_time),
    CHECK (is_hot_sale IN (0, 1)),
    CHECK (is_new IN (0, 1)),
    CHECK (is_current IN (0, 1)),
    CHECK (is_deleted IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'SKU一致性维度拉链表';

CREATE TABLE dim_promotion_rule_version (
    promotion_version_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '促销规则版本代理键',
    promotion_id BIGINT UNSIGNED NOT NULL COMMENT '促销活动业务ID',
    rule_version_no INT UNSIGNED NOT NULL COMMENT '促销规则业务版本号',
    promotion_name VARCHAR(256) NOT NULL COMMENT '活动名称',
    promotion_type VARCHAR(32) NOT NULL COMMENT '活动类型',
    promotion_scene VARCHAR(32) NOT NULL COMMENT '活动场景',
    promotion_priority SMALLINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '活动优先级',
    activity_start_time DATETIME(6) NOT NULL COMMENT '活动开始时间',
    activity_end_time DATETIME(6) NOT NULL COMMENT '活动结束时间',
    rule_effective_start_time DATETIME(6) NOT NULL COMMENT '规则版本生效时间',
    rule_effective_end_time DATETIME(6) NOT NULL COMMENT '规则版本失效时间',
    rule_description VARCHAR(2000) DEFAULT NULL COMMENT '规则说明',
    threshold_amount DECIMAL(18, 2) DEFAULT NULL COMMENT '优惠门槛金额',
    discount_amount DECIMAL(18, 2) DEFAULT NULL COMMENT '固定优惠金额',
    discount_rate DECIMAL(10, 6) DEFAULT NULL COMMENT '优惠折扣率',
    max_discount_amount DECIMAL(18, 2) DEFAULT NULL COMMENT '最大优惠金额',
    sponsor_type VARCHAR(32) NOT NULL COMMENT '发起方类型',
    sponsor_business_id VARCHAR(64) DEFAULT NULL COMMENT '发起方业务ID',
    promotion_status VARCHAR(16) NOT NULL COMMENT '该规则版本发布状态',
    rule_hash CHAR(64) NOT NULL COMMENT '规则内容哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (promotion_version_sk),
    UNIQUE KEY uk_promotion_rule_version (promotion_id, rule_version_no),
    UNIQUE KEY uk_promotion_rule_start (
        promotion_id, rule_effective_start_time
    ),
    KEY idx_promotion_activity_time (activity_start_time, activity_end_time),
    KEY idx_promotion_rule_effective (
        promotion_id,
        rule_effective_start_time,
        rule_effective_end_time
    ),
    CHECK (rule_version_no > 0),
    CHECK (activity_start_time < activity_end_time),
    CHECK (rule_effective_start_time < rule_effective_end_time),
    CHECK (threshold_amount IS NULL OR threshold_amount >= 0),
    CHECK (discount_amount IS NULL OR discount_amount >= 0),
    CHECK (discount_rate IS NULL OR discount_rate BETWEEN 0 AND 1),
    CHECK (max_discount_amount IS NULL OR max_discount_amount >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '促销活动不可变规则版本维度';

CREATE TABLE bridge_promotion_scope (
    promotion_scope_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '活动范围关系代理键',
    promotion_version_sk BIGINT NOT NULL COMMENT '促销规则版本代理键',
    promotion_id BIGINT UNSIGNED NOT NULL COMMENT '促销活动业务ID',
    scope_type VARCHAR(32) NOT NULL COMMENT '适用对象类型',
    scope_business_id VARCHAR(64) NOT NULL COMMENT '适用对象业务ID',
    is_excluded TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否排除对象:0否 1是',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (promotion_scope_sk),
    UNIQUE KEY uk_promotion_scope (
        promotion_version_sk,
        scope_type,
        scope_business_id
    ),
    KEY idx_promotion_scope_target (scope_type, scope_business_id),
    CHECK (is_excluded IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '促销规则版本适用范围桥表';

CREATE TABLE dim_coupon_template_version (
    coupon_template_version_sk BIGINT NOT NULL AUTO_INCREMENT
    COMMENT '优惠券规则版本代理键',
    coupon_template_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券模板业务ID',
    rule_version_no INT UNSIGNED NOT NULL COMMENT '优惠券规则业务版本号',
    coupon_name VARCHAR(256) NOT NULL COMMENT '优惠券名称',
    coupon_type VARCHAR(32) NOT NULL COMMENT '优惠券类型',
    threshold_amount DECIMAL(18, 2) DEFAULT NULL COMMENT '使用门槛金额',
    discount_amount DECIMAL(18, 2) DEFAULT NULL COMMENT '固定优惠金额',
    discount_rate DECIMAL(10, 6) DEFAULT NULL COMMENT '优惠折扣率',
    max_discount_amount DECIMAL(18, 2) DEFAULT NULL COMMENT '最大优惠金额',
    issue_start_time DATETIME(6) NOT NULL COMMENT '发券开始时间',
    issue_end_time DATETIME(6) NOT NULL COMMENT '发券结束时间',
    use_start_time DATETIME(6) NOT NULL COMMENT '可用开始时间',
    use_end_time DATETIME(6) NOT NULL COMMENT '可用结束时间',
    rule_effective_start_time DATETIME(6) NOT NULL COMMENT '规则版本生效时间',
    rule_effective_end_time DATETIME(6) NOT NULL COMMENT '规则版本失效时间',
    total_issue_limit BIGINT UNSIGNED DEFAULT NULL COMMENT '最大发行量',
    per_user_limit INT UNSIGNED DEFAULT NULL COMMENT '单用户领取上限',
    coupon_status VARCHAR(16) NOT NULL COMMENT '该规则版本发布状态',
    rule_hash CHAR(64) NOT NULL COMMENT '规则内容哈希',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_update_time DATETIME(6) DEFAULT NULL COMMENT '源系统更新时间',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (coupon_template_version_sk),
    UNIQUE KEY uk_coupon_rule_version (coupon_template_id, rule_version_no),
    UNIQUE KEY uk_coupon_rule_start (
        coupon_template_id,
        rule_effective_start_time
    ),
    KEY idx_coupon_issue_time (issue_start_time, issue_end_time),
    KEY idx_coupon_use_time (use_start_time, use_end_time),
    KEY idx_coupon_rule_effective (
        coupon_template_id,
        rule_effective_start_time,
        rule_effective_end_time
    ),
    CHECK (rule_version_no > 0),
    CHECK (issue_start_time < issue_end_time),
    CHECK (use_start_time < use_end_time),
    CHECK (rule_effective_start_time < rule_effective_end_time),
    CHECK (threshold_amount IS NULL OR threshold_amount >= 0),
    CHECK (discount_amount IS NULL OR discount_amount >= 0),
    CHECK (discount_rate IS NULL OR discount_rate BETWEEN 0 AND 1),
    CHECK (max_discount_amount IS NULL OR max_discount_amount >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '优惠券模板不可变规则版本维度';

CREATE TABLE bridge_coupon_scope (
    coupon_scope_sk BIGINT NOT NULL AUTO_INCREMENT COMMENT '优惠券范围关系代理键',
    coupon_template_version_sk BIGINT NOT NULL COMMENT '优惠券规则版本代理键',
    coupon_template_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券模板业务ID',
    scope_type VARCHAR(32) NOT NULL COMMENT '适用对象类型',
    scope_business_id VARCHAR(64) NOT NULL COMMENT '适用对象业务ID',
    is_excluded TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否排除对象:0否 1是',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (coupon_scope_sk),
    UNIQUE KEY uk_coupon_scope (
        coupon_template_version_sk,
        scope_type,
        scope_business_id
    ),
    KEY idx_coupon_scope_target (scope_type, scope_business_id),
    CHECK (is_excluded IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '优惠券规则版本适用范围桥表';

/* =========================
   DWD 商品域原子事实
   ========================= */

-- 粒度：一行代表一个SKU基础价格方案发生的一次生效变更
CREATE TABLE dwd_product_sku_price_change_di (
    price_change_id BIGINT UNSIGNED NOT NULL COMMENT '价格变更事件业务ID',
    event_date_key INT UNSIGNED NOT NULL COMMENT '价格生效日期键',
    sku_sk BIGINT NOT NULL COMMENT '价格生效时SKU版本代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU业务ID',
    spu_sk BIGINT NOT NULL COMMENT '价格生效时SPU版本代理键',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU业务ID',
    shop_sk BIGINT NOT NULL COMMENT '价格生效时店铺版本代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    category_sk BIGINT NOT NULL COMMENT '价格生效时类目版本代理键',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '类目业务ID',
    brand_sk BIGINT NOT NULL DEFAULT -1 COMMENT '价格生效时品牌代理键',
    brand_id BIGINT UNSIGNED DEFAULT NULL COMMENT '品牌业务ID',
    previous_list_price DECIMAL(18, 4) DEFAULT NULL COMMENT '变更前吊牌单价',
    previous_sale_price DECIMAL(18, 4) DEFAULT NULL COMMENT '变更前销售单价',
    previous_cost_price DECIMAL(18, 4) DEFAULT NULL COMMENT '变更前标准成本单价',
    new_list_price DECIMAL(18, 4) NOT NULL COMMENT '变更后吊牌单价',
    new_sale_price DECIMAL(18, 4) NOT NULL COMMENT '变更后销售单价',
    new_cost_price DECIMAL(18, 4) DEFAULT NULL COMMENT '变更后标准成本单价',
    change_reason_code VARCHAR(32) DEFAULT NULL COMMENT '价格变更原因编码',
    change_reason_description VARCHAR(512) DEFAULT NULL COMMENT '价格变更原因说明',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    price_effective_time DATETIME(6) NOT NULL COMMENT '新价格生效时间',
    change_time DATETIME(6) NOT NULL COMMENT '价格配置变更时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取新价格生效日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (price_change_id),
    UNIQUE KEY uk_sku_price_source (source_system_code, source_record_id),
    KEY idx_sku_price_effective (sku_sk, price_effective_time),
    KEY idx_shop_price_date (shop_sk, biz_date),
    CHECK (previous_list_price IS NULL OR previous_list_price >= 0),
    CHECK (previous_sale_price IS NULL OR previous_sale_price >= 0),
    CHECK (previous_cost_price IS NULL OR previous_cost_price >= 0),
    CHECK (new_list_price >= 0),
    CHECK (new_sale_price >= 0),
    CHECK (new_cost_price IS NULL OR new_cost_price >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '商品域SKU基础价格变更事件事实';

/* =========================
   DWD 交易域原子事实
   ========================= */

-- 粒度：一行代表一个订单商品明细在下单时形成的不可变交易事实
CREATE TABLE dwd_trade_order_detail_di (
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细业务ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    parent_order_id BIGINT UNSIGNED DEFAULT NULL COMMENT '父订单业务ID',
    trade_no VARCHAR(64) DEFAULT NULL COMMENT '交易流水号',
    order_no VARCHAR(64) NOT NULL COMMENT '订单编号',
    order_date_key INT UNSIGNED NOT NULL COMMENT '下单日期键',
    user_sk BIGINT NOT NULL COMMENT '下单时用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    shop_sk BIGINT NOT NULL COMMENT '下单时店铺版本代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    seller_sk BIGINT NOT NULL DEFAULT -1 COMMENT '下单时商家版本代理键',
    seller_id BIGINT UNSIGNED DEFAULT NULL COMMENT '商家业务ID',
    sku_sk BIGINT NOT NULL COMMENT '下单时SKU版本代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU业务ID',
    spu_sk BIGINT NOT NULL COMMENT '下单时SPU版本代理键',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU业务ID',
    category_sk BIGINT NOT NULL COMMENT '下单时叶子类目版本代理键',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '叶子类目业务ID',
    brand_sk BIGINT NOT NULL DEFAULT -1 COMMENT '品牌代理键',
    brand_id BIGINT UNSIGNED DEFAULT NULL COMMENT '品牌业务ID',
    receiver_region_sk BIGINT NOT NULL DEFAULT -1 COMMENT '收货区县版本代理键',
    receiver_region_code VARCHAR(20) DEFAULT NULL COMMENT '收货区县编码',
    channel_sk BIGINT NOT NULL DEFAULT -1 COMMENT '下单渠道代理键',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '下单渠道编码',
    order_source VARCHAR(32) DEFAULT NULL COMMENT '下单来源',
    order_scene VARCHAR(32) NOT NULL DEFAULT '普通' COMMENT '订单场景',
    is_first_order TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否用户首单:0否 1是',
    is_cross_border TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否跨境订单:0否 1是',
    is_presale TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否预售订单:0否 1是',
    is_gift TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否赠品:0否 1是',
    is_risk_order TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否风险订单:0否 1是',
    sku_qty INT UNSIGNED NOT NULL COMMENT '购买件数',
    sku_list_unit_price DECIMAL(18, 4) NOT NULL COMMENT '商品吊牌单价快照',
    sku_sale_unit_price DECIMAL(18, 4) NOT NULL COMMENT '商品销售单价快照',
    list_amount DECIMAL(18, 2) NOT NULL COMMENT '吊牌金额',
    sale_amount DECIMAL(18, 2) NOT NULL COMMENT '优惠前销售金额',
    activity_discount_amount DECIMAL(
        18, 2
    ) NOT NULL DEFAULT 0 COMMENT '活动优惠分摊金额',
    coupon_discount_amount DECIMAL(
        18, 2
    ) NOT NULL DEFAULT 0 COMMENT '优惠券优惠分摊金额',
    points_discount_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '积分优惠分摊金额',
    freight_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '运费分摊金额',
    tax_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '税费分摊金额',
    receivable_amount DECIMAL(18, 2) NOT NULL COMMENT '下单应收金额',
    cost_amount DECIMAL(18, 2) DEFAULT NULL COMMENT '下单时标准成本金额快照',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    order_create_time DATETIME(6) NOT NULL COMMENT '下单时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取下单日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (order_detail_id),
    UNIQUE KEY uk_order_source_record (source_system_code, source_record_id),
    KEY idx_order_id (order_id),
    KEY idx_order_date_shop (biz_date, shop_sk),
    KEY idx_order_user_date (user_sk, biz_date),
    KEY idx_order_sku_date (sku_sk, biz_date),
    KEY idx_order_category_date (category_sk, biz_date),
    CHECK (is_first_order IN (0, 1)),
    CHECK (is_cross_border IN (0, 1)),
    CHECK (is_presale IN (0, 1)),
    CHECK (is_gift IN (0, 1)),
    CHECK (is_risk_order IN (0, 1)),
    CHECK (sku_qty > 0),
    CHECK (sku_list_unit_price >= 0),
    CHECK (sku_sale_unit_price >= 0),
    CHECK (list_amount >= 0),
    CHECK (sale_amount >= 0),
    CHECK (activity_discount_amount >= 0),
    CHECK (coupon_discount_amount >= 0),
    CHECK (points_discount_amount >= 0),
    CHECK (freight_amount >= 0),
    CHECK (tax_amount >= 0),
    CHECK (receivable_amount >= 0),
    CHECK (cost_amount IS NULL OR cost_amount >= 0),
    CHECK (list_amount = ROUND(sku_list_unit_price * sku_qty, 2)),
    CHECK (sale_amount = ROUND(sku_sale_unit_price * sku_qty, 2)),
    CHECK (
        receivable_amount = sale_amount
        - activity_discount_amount
        - coupon_discount_amount
        - points_discount_amount
        + freight_amount
        + tax_amount
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域下单明细事务事实';

-- 粒度：一行代表一个订单发生的一次状态迁移事件
CREATE TABLE dwd_trade_order_status_event_di (
    order_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '订单状态事件业务ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    event_seq_no INT UNSIGNED NOT NULL COMMENT '订单内事件序号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    user_sk BIGINT NOT NULL COMMENT '事件时点用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    shop_sk BIGINT NOT NULL COMMENT '事件时点店铺版本代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    before_order_status VARCHAR(32) DEFAULT NULL COMMENT '变更前订单状态',
    after_order_status VARCHAR(32) NOT NULL COMMENT '变更后订单状态',
    status_event_type VARCHAR(32) NOT NULL COMMENT '状态事件类型',
    status_reason_code VARCHAR(32) DEFAULT NULL COMMENT '状态原因编码',
    status_reason_description VARCHAR(512) DEFAULT NULL COMMENT '状态原因说明',
    cancel_stage VARCHAR(32) DEFAULT NULL COMMENT '取消阶段',
    is_terminal_status TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否终态:0否 1是',
    operator_id VARCHAR(64) DEFAULT NULL COMMENT '操作人业务ID',
    operator_type VARCHAR(32) DEFAULT NULL COMMENT '操作人类型',
    event_time DATETIME(6) NOT NULL COMMENT '状态变更时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取状态变更日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (order_status_event_id),
    UNIQUE KEY uk_order_status_seq (order_id, event_seq_no),
    UNIQUE KEY uk_order_status_source (source_system_code, source_record_id),
    KEY idx_order_status_date (biz_date, after_order_status),
    KEY idx_order_status_order_time (order_id, event_time),
    CHECK (event_seq_no > 0),
    CHECK (is_terminal_status IN (0, 1))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域订单状态迁移事件事实';

-- 粒度：一行代表一个订单明细分摊到一个促销活动版本的优惠事实
CREATE TABLE dwd_trade_order_detail_activity_di (
    order_detail_activity_id BIGINT UNSIGNED NOT NULL COMMENT '订单活动分摊业务ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细业务ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    promotion_version_sk BIGINT NOT NULL COMMENT '下单命中的促销规则版本代理键',
    promotion_id BIGINT UNSIGNED NOT NULL COMMENT '促销活动业务ID',
    promotion_discount_amount DECIMAL(18, 2) NOT NULL COMMENT '活动优惠分摊金额',
    rule_snapshot_json JSON DEFAULT NULL COMMENT '命中规则快照',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    order_create_time DATETIME(6) NOT NULL COMMENT '下单时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取下单日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (order_detail_activity_id),
    UNIQUE KEY uk_order_detail_promotion (
        order_detail_id, promotion_version_sk
    ),
    UNIQUE KEY uk_order_activity_source (source_system_code, source_record_id),
    KEY idx_activity_promotion_date (promotion_version_sk, biz_date),
    KEY idx_activity_order (order_id),
    CHECK (promotion_discount_amount > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域订单明细活动优惠分摊事实';

-- 粒度：一行代表一个订单明细分摊到一个用户优惠券实例的优惠事实
CREATE TABLE dwd_trade_order_detail_coupon_di (
    order_detail_coupon_id BIGINT UNSIGNED NOT NULL COMMENT '订单优惠券分摊业务ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细业务ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    coupon_template_version_sk BIGINT NOT NULL COMMENT '用券命中的优惠券规则版本代理键',
    coupon_template_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券模板业务ID',
    user_coupon_id BIGINT UNSIGNED NOT NULL COMMENT '用户优惠券实例ID',
    user_sk BIGINT NOT NULL COMMENT '用券时用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    coupon_discount_amount DECIMAL(18, 2) NOT NULL COMMENT '优惠券优惠分摊金额',
    coupon_batch_no VARCHAR(64) DEFAULT NULL COMMENT '发券批次号',
    coupon_receive_time DATETIME(6) DEFAULT NULL COMMENT '领券时间',
    coupon_use_time DATETIME(6) NOT NULL COMMENT '用券时间',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    order_create_time DATETIME(6) NOT NULL COMMENT '下单时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取下单日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (order_detail_coupon_id),
    UNIQUE KEY uk_order_detail_user_coupon (order_detail_id, user_coupon_id),
    UNIQUE KEY uk_order_coupon_source (source_system_code, source_record_id),
    KEY idx_coupon_template_date (coupon_template_version_sk, biz_date),
    KEY idx_user_coupon (user_coupon_id),
    KEY idx_coupon_order (order_id),
    CHECK (coupon_discount_amount > 0),
    CHECK (
        coupon_receive_time IS NULL OR coupon_receive_time <= coupon_use_time
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域订单明细优惠券优惠分摊事实';

/* =========================
   DWD 营销域原子事实
   ========================= */

-- 粒度：一行代表一个用户优惠券实例发生的一次生命周期事件
CREATE TABLE dwd_marketing_user_coupon_event_di (
    user_coupon_event_id BIGINT UNSIGNED NOT NULL COMMENT '用户券事件业务ID',
    user_coupon_id BIGINT UNSIGNED NOT NULL COMMENT '用户优惠券实例ID',
    event_seq_no INT UNSIGNED NOT NULL COMMENT '用户券实例内事件序号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    coupon_template_version_sk BIGINT NOT NULL COMMENT '事件命中的优惠券规则版本代理键',
    coupon_template_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券模板业务ID',
    user_sk BIGINT NOT NULL COMMENT '事件时点用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    before_coupon_status VARCHAR(32) DEFAULT NULL COMMENT '变更前用户券状态',
    after_coupon_status VARCHAR(32) NOT NULL COMMENT '变更后用户券状态',
    coupon_event_type VARCHAR(32) NOT NULL COMMENT '事件类型:领取/锁定/使用/释放/过期/作废',
    related_order_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联订单业务ID',
    coupon_batch_no VARCHAR(64) DEFAULT NULL COMMENT '发券批次号',
    event_time DATETIME(6) NOT NULL COMMENT '事件发生时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取事件发生日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (user_coupon_event_id),
    UNIQUE KEY uk_user_coupon_event_seq (user_coupon_id, event_seq_no),
    UNIQUE KEY uk_user_coupon_event_source (
        source_system_code, source_record_id
    ),
    KEY idx_user_coupon_event_date (biz_date, coupon_event_type),
    KEY idx_coupon_template_user (coupon_template_version_sk, user_sk),
    CHECK (event_seq_no > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '营销域用户优惠券生命周期事件事实';

/* =========================
   DWD 支付域原子事实
   ========================= */

-- 粒度：一行代表一个支付单使用一种支付工具发起的一次支付尝试
CREATE TABLE dwd_trade_pay_detail_di (
    pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '支付尝试业务ID',
    pay_order_no VARCHAR(64) NOT NULL COMMENT '支付单号',
    pay_attempt_no INT UNSIGNED NOT NULL COMMENT '支付单内尝试序号',
    pay_date_key INT UNSIGNED NOT NULL COMMENT '支付请求日期键',
    user_sk BIGINT NOT NULL COMMENT '支付请求时用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    payment_type_sk BIGINT NOT NULL COMMENT '支付方式代理键',
    payment_type_code VARCHAR(32) NOT NULL COMMENT '支付方式业务编码',
    channel_sk BIGINT NOT NULL DEFAULT -1 COMMENT '支付渠道代理键',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '支付渠道编码',
    pay_scene VARCHAR(32) NOT NULL COMMENT '支付场景',
    requested_pay_amount DECIMAL(18, 2) NOT NULL COMMENT '本次请求支付金额',
    payment_fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '支付手续费金额',
    installment_count INT UNSIGNED DEFAULT NULL COMMENT '分期期数',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    pay_request_time DATETIME(6) NOT NULL COMMENT '支付请求时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取支付请求日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (pay_detail_id),
    UNIQUE KEY uk_pay_attempt (pay_order_no, pay_attempt_no),
    UNIQUE KEY uk_pay_source_record (source_system_code, source_record_id),
    KEY idx_pay_user_date (user_sk, biz_date),
    KEY idx_pay_type_date (payment_type_sk, biz_date),
    CHECK (pay_attempt_no > 0),
    CHECK (requested_pay_amount > 0),
    CHECK (payment_fee_amount >= 0),
    CHECK (installment_count IS NULL OR installment_count > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '支付域支付尝试事务事实';

-- 粒度：一行代表一次支付尝试分摊到一个订单明细的结算金额
CREATE TABLE dwd_trade_pay_order_detail_di (
    pay_order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '支付分摊业务ID',
    pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '支付尝试业务ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细业务ID',
    shop_sk BIGINT NOT NULL COMMENT '支付时店铺版本代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    seller_sk BIGINT NOT NULL DEFAULT -1 COMMENT '支付时商家版本代理键',
    seller_id BIGINT UNSIGNED DEFAULT NULL COMMENT '商家业务ID',
    allocated_pay_amount DECIMAL(18, 2) NOT NULL COMMENT '支付分摊金额',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    pay_request_time DATETIME(6) NOT NULL COMMENT '支付请求时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取支付请求日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (pay_order_detail_id),
    UNIQUE KEY uk_pay_order_detail (pay_detail_id, order_detail_id),
    UNIQUE KEY uk_pay_allocation_source (source_system_code, source_record_id),
    KEY idx_pay_allocation_order (order_id, order_detail_id),
    KEY idx_pay_allocation_shop_date (shop_sk, biz_date),
    CHECK (allocated_pay_amount > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '支付域支付到订单明细分摊事实';

-- 粒度：一行代表一次支付尝试发生的一次状态迁移事件
CREATE TABLE dwd_trade_pay_status_event_di (
    pay_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '支付状态事件业务ID',
    pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '支付尝试业务ID',
    pay_order_no VARCHAR(64) NOT NULL COMMENT '支付单号',
    event_seq_no INT UNSIGNED NOT NULL COMMENT '支付尝试内事件序号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    third_party_pay_no VARCHAR(128) DEFAULT NULL COMMENT '第三方支付流水号',
    before_pay_status VARCHAR(32) DEFAULT NULL COMMENT '变更前支付状态',
    after_pay_status VARCHAR(32) NOT NULL COMMENT '变更后支付状态',
    status_reason_code VARCHAR(32) DEFAULT NULL COMMENT '状态原因编码',
    status_reason_description VARCHAR(512) DEFAULT NULL COMMENT '状态原因说明',
    event_time DATETIME(6) NOT NULL COMMENT '状态变更时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取状态变更日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (pay_status_event_id),
    UNIQUE KEY uk_pay_status_seq (pay_detail_id, event_seq_no),
    UNIQUE KEY uk_pay_status_source (source_system_code, source_record_id),
    KEY idx_pay_status_date (biz_date, after_pay_status),
    KEY idx_pay_status_time (pay_detail_id, event_time),
    KEY idx_third_party_pay_no (third_party_pay_no),
    CHECK (event_seq_no > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '支付域支付状态迁移事件事实';

/* =========================
   DWD 履约域原子事实
   ========================= */

-- 粒度：一行代表一个正向或逆向物流包裹
CREATE TABLE dwd_trade_delivery_di (
    delivery_id BIGINT UNSIGNED NOT NULL COMMENT '物流包裹业务ID',
    delivery_no VARCHAR(64) NOT NULL COMMENT '物流单号',
    package_no VARCHAR(64) NOT NULL COMMENT '包裹编号',
    delivery_direction VARCHAR(16) NOT NULL COMMENT '物流方向:正向/逆向',
    delivery_date_key INT UNSIGNED NOT NULL COMMENT '包裹创建日期键',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    refund_no VARCHAR(64) DEFAULT NULL COMMENT '关联退款单号',
    user_sk BIGINT NOT NULL COMMENT '包裹创建时用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    shop_sk BIGINT NOT NULL COMMENT '包裹创建时店铺版本代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    seller_sk BIGINT NOT NULL DEFAULT -1 COMMENT '包裹创建时商家版本代理键',
    seller_id BIGINT UNSIGNED DEFAULT NULL COMMENT '商家业务ID',
    warehouse_sk BIGINT NOT NULL COMMENT '出入库仓库版本代理键',
    warehouse_id BIGINT UNSIGNED NOT NULL COMMENT '仓库业务ID',
    logistics_company_sk BIGINT NOT NULL DEFAULT -1 COMMENT '物流公司代理键',
    logistics_company_id BIGINT UNSIGNED DEFAULT NULL COMMENT '物流公司业务ID',
    receiver_region_sk BIGINT NOT NULL DEFAULT -1 COMMENT '收件区县版本代理键',
    receiver_region_code VARCHAR(20) DEFAULT NULL COMMENT '收件区县编码',
    tracking_no VARCHAR(128) DEFAULT NULL COMMENT '运单号',
    delivery_type VARCHAR(32) NOT NULL COMMENT '配送类型',
    receiver_name VARCHAR(64) DEFAULT NULL COMMENT '收件人脱敏值',
    receiver_phone VARCHAR(20) DEFAULT NULL COMMENT '收件电话脱敏值',
    receiver_address VARCHAR(512) DEFAULT NULL COMMENT '收件地址脱敏值',
    package_weight_kg DECIMAL(18, 3) NOT NULL DEFAULT 0 COMMENT '包裹重量千克',
    package_freight_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '包裹运费金额',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    delivery_create_time DATETIME(6) NOT NULL COMMENT '包裹创建时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取包裹创建日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (delivery_id),
    UNIQUE KEY uk_delivery_package (package_no),
    UNIQUE KEY uk_delivery_source (source_system_code, source_record_id),
    KEY idx_delivery_order (order_id),
    KEY idx_delivery_refund (refund_no),
    KEY idx_delivery_tracking (tracking_no),
    KEY idx_delivery_warehouse_date (warehouse_sk, biz_date),
    KEY idx_delivery_logistics_date (logistics_company_sk, biz_date),
    CHECK (package_weight_kg >= 0),
    CHECK (package_freight_amount >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '履约域物流包裹事务事实';

-- 粒度：一行代表一个物流包裹承载的一个订单明细或退款明细
CREATE TABLE dwd_trade_delivery_item_di (
    delivery_item_id BIGINT UNSIGNED NOT NULL COMMENT '包裹商品明细业务ID',
    delivery_id BIGINT UNSIGNED NOT NULL COMMENT '物流包裹业务ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细业务ID',
    refund_detail_id BIGINT UNSIGNED DEFAULT NULL COMMENT '退款明细业务ID',
    sku_sk BIGINT NOT NULL COMMENT '包裹创建时SKU版本代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU业务ID',
    spu_sk BIGINT NOT NULL COMMENT '包裹创建时SPU版本代理键',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU业务ID',
    category_sk BIGINT NOT NULL COMMENT '包裹创建时类目版本代理键',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '类目业务ID',
    delivery_sku_qty INT UNSIGNED NOT NULL COMMENT '本包裹商品件数',
    allocated_weight_kg DECIMAL(18, 3) NOT NULL DEFAULT 0 COMMENT '商品分摊重量千克',
    allocated_freight_amount DECIMAL(
        18, 2
    ) NOT NULL DEFAULT 0 COMMENT '商品分摊运费金额',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    delivery_create_time DATETIME(6) NOT NULL COMMENT '包裹创建时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取包裹创建日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (delivery_item_id),
    UNIQUE KEY uk_delivery_item_source (source_system_code, source_record_id),
    KEY idx_delivery_item_delivery (delivery_id),
    KEY idx_delivery_item_order (order_id, order_detail_id),
    KEY idx_delivery_item_refund (refund_detail_id),
    KEY idx_delivery_item_sku_date (sku_sk, biz_date),
    CHECK (delivery_sku_qty > 0),
    CHECK (allocated_weight_kg >= 0),
    CHECK (allocated_freight_amount >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '履约域物流包裹商品明细事实';

-- 粒度：一行代表一个物流包裹发生的一次状态迁移事件
CREATE TABLE dwd_trade_delivery_status_event_di (
    delivery_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '物流状态事件业务ID',
    delivery_id BIGINT UNSIGNED NOT NULL COMMENT '物流包裹业务ID',
    event_seq_no INT UNSIGNED NOT NULL COMMENT '包裹内事件序号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    before_delivery_status VARCHAR(32) DEFAULT NULL COMMENT '变更前物流状态',
    after_delivery_status VARCHAR(32) NOT NULL COMMENT '变更后物流状态',
    status_event_code VARCHAR(32) NOT NULL COMMENT '物流事件编码',
    event_region_sk BIGINT NOT NULL DEFAULT -1 COMMENT '事件地点区域版本代理键',
    event_region_code VARCHAR(20) DEFAULT NULL COMMENT '事件地点区域编码',
    event_location VARCHAR(256) DEFAULT NULL COMMENT '事件地点说明',
    event_remark VARCHAR(512) DEFAULT NULL COMMENT '物流事件说明',
    event_time DATETIME(6) NOT NULL COMMENT '状态变更时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取状态变更日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (delivery_status_event_id),
    UNIQUE KEY uk_delivery_status_seq (delivery_id, event_seq_no),
    UNIQUE KEY uk_delivery_status_source (source_system_code, source_record_id),
    KEY idx_delivery_status_date (biz_date, after_delivery_status),
    KEY idx_delivery_status_time (delivery_id, event_time),
    CHECK (event_seq_no > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '履约域物流状态迁移事件事实';

/* =========================
   DWD 退款域原子事实
   ========================= */

-- 粒度：一行代表一个退款申请中的一个订单商品明细
CREATE TABLE dwd_trade_refund_detail_di (
    refund_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款明细业务ID',
    refund_no VARCHAR(64) NOT NULL COMMENT '退款单号',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细业务ID',
    apply_date_key INT UNSIGNED NOT NULL COMMENT '退款申请日期键',
    user_sk BIGINT NOT NULL COMMENT '申请时用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    shop_sk BIGINT NOT NULL COMMENT '申请时店铺版本代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    seller_sk BIGINT NOT NULL DEFAULT -1 COMMENT '申请时商家版本代理键',
    seller_id BIGINT UNSIGNED DEFAULT NULL COMMENT '商家业务ID',
    sku_sk BIGINT NOT NULL COMMENT '申请时SKU版本代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU业务ID',
    refund_sku_qty INT UNSIGNED NOT NULL COMMENT '申请退款商品件数',
    refund_type VARCHAR(32) NOT NULL COMMENT '退款类型',
    refund_reason_code VARCHAR(32) DEFAULT NULL COMMENT '退款原因编码',
    refund_reason_description VARCHAR(256) DEFAULT NULL COMMENT '退款原因说明',
    is_quality_issue TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否质量问题:0否 1是',
    need_return_goods TINYINT UNSIGNED NOT NULL DEFAULT 0
    COMMENT '是否需要退货:0否 1是',
    apply_goods_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '申请退商品金额',
    apply_freight_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '申请退运费金额',
    apply_tax_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '申请退税金额',
    refund_apply_amount DECIMAL(18, 2) NOT NULL COMMENT '申请退款总金额',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    apply_time DATETIME(6) NOT NULL COMMENT '退款申请时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取退款申请日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (refund_detail_id),
    UNIQUE KEY uk_refund_detail_source (source_system_code, source_record_id),
    KEY idx_refund_no (refund_no),
    KEY idx_refund_order_detail (order_id, order_detail_id),
    KEY idx_refund_user_date (user_sk, biz_date),
    KEY idx_refund_shop_date (shop_sk, biz_date),
    CHECK (refund_sku_qty > 0),
    CHECK (is_quality_issue IN (0, 1)),
    CHECK (need_return_goods IN (0, 1)),
    CHECK (apply_goods_amount >= 0),
    CHECK (apply_freight_amount >= 0),
    CHECK (apply_tax_amount >= 0),
    CHECK (refund_apply_amount > 0),
    CHECK (
        refund_apply_amount = apply_goods_amount
        + apply_freight_amount
        + apply_tax_amount
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '退款域退款申请商品明细事实';

-- 粒度：一行代表一个退款明细发生的一次状态迁移事件
CREATE TABLE dwd_trade_refund_status_event_di (
    refund_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '退款状态事件业务ID',
    refund_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款明细业务ID',
    refund_no VARCHAR(64) NOT NULL COMMENT '退款单号',
    event_seq_no INT UNSIGNED NOT NULL COMMENT '退款明细内事件序号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    before_refund_status VARCHAR(32) DEFAULT NULL COMMENT '变更前退款状态',
    after_refund_status VARCHAR(32) NOT NULL COMMENT '变更后退款状态',
    approved_amount_delta DECIMAL(18, 2) DEFAULT NULL COMMENT '本事件新确认的审核通过金额',
    status_reason_code VARCHAR(32) DEFAULT NULL COMMENT '状态原因编码',
    status_reason_description VARCHAR(512) DEFAULT NULL COMMENT '状态原因说明',
    operator_id VARCHAR(64) DEFAULT NULL COMMENT '操作人业务ID',
    operator_type VARCHAR(32) DEFAULT NULL COMMENT '操作人类型',
    event_time DATETIME(6) NOT NULL COMMENT '状态变更时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取状态变更日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (refund_status_event_id),
    UNIQUE KEY uk_refund_status_seq (refund_detail_id, event_seq_no),
    UNIQUE KEY uk_refund_status_source (source_system_code, source_record_id),
    KEY idx_refund_status_date (biz_date, after_refund_status),
    KEY idx_refund_status_time (refund_detail_id, event_time),
    CHECK (event_seq_no > 0),
    CHECK (approved_amount_delta IS NULL OR approved_amount_delta >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '退款域退款状态迁移事件事实';

-- 粒度：一行代表一次退款资金渠道打款尝试
CREATE TABLE dwd_trade_refund_pay_detail_di (
    refund_pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款打款尝试业务ID',
    refund_no VARCHAR(64) NOT NULL COMMENT '退款单号',
    refund_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款明细业务ID',
    refund_pay_attempt_no INT UNSIGNED NOT NULL COMMENT '退款明细内打款尝试序号',
    original_pay_detail_id BIGINT UNSIGNED DEFAULT NULL COMMENT '原支付尝试业务ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细业务ID',
    request_date_key INT UNSIGNED NOT NULL COMMENT '退款打款请求日期键',
    user_sk BIGINT NOT NULL COMMENT '打款请求时用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    payment_type_sk BIGINT NOT NULL COMMENT '原支付方式代理键',
    payment_type_code VARCHAR(32) NOT NULL COMMENT '原支付方式业务编码',
    channel_sk BIGINT NOT NULL DEFAULT -1 COMMENT '退款渠道代理键',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '退款渠道编码',
    refund_goods_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '退商品金额',
    refund_freight_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '退运费金额',
    refund_tax_amount DECIMAL(18, 2) NOT NULL DEFAULT 0 COMMENT '退税金额',
    refund_amount DECIMAL(18, 2) NOT NULL COMMENT '退款打款总金额',
    refund_account_type VARCHAR(32) NOT NULL COMMENT '退款账户类型',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    refund_pay_request_time DATETIME(6) NOT NULL COMMENT '退款打款请求时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取退款打款请求日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (refund_pay_detail_id),
    UNIQUE KEY uk_refund_pay_attempt (refund_detail_id, refund_pay_attempt_no),
    UNIQUE KEY uk_refund_pay_source (source_system_code, source_record_id),
    KEY idx_refund_pay_no (refund_no),
    KEY idx_refund_pay_original (original_pay_detail_id),
    KEY idx_refund_pay_user_date (user_sk, biz_date),
    CHECK (refund_pay_attempt_no > 0),
    CHECK (refund_goods_amount >= 0),
    CHECK (refund_freight_amount >= 0),
    CHECK (refund_tax_amount >= 0),
    CHECK (refund_amount > 0),
    CHECK (
        refund_amount = refund_goods_amount
        + refund_freight_amount
        + refund_tax_amount
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '退款域退款打款尝试事务事实';

-- 粒度：一行代表一次退款打款尝试发生的一次状态迁移事件
CREATE TABLE dwd_trade_refund_pay_status_event_di (
    refund_pay_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '退款打款状态事件业务ID',
    refund_pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款打款尝试业务ID',
    event_seq_no INT UNSIGNED NOT NULL COMMENT '打款尝试内事件序号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    third_party_refund_no VARCHAR(128) DEFAULT NULL COMMENT '第三方退款流水号',
    before_refund_pay_status VARCHAR(32) DEFAULT NULL COMMENT '变更前打款状态',
    after_refund_pay_status VARCHAR(32) NOT NULL COMMENT '变更后打款状态',
    status_reason_code VARCHAR(32) DEFAULT NULL COMMENT '状态原因编码',
    status_reason_description VARCHAR(512) DEFAULT NULL COMMENT '状态原因说明',
    event_time DATETIME(6) NOT NULL COMMENT '状态变更时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取状态变更日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (refund_pay_status_event_id),
    UNIQUE KEY uk_refund_pay_status_seq (refund_pay_detail_id, event_seq_no),
    UNIQUE KEY uk_refund_pay_status_source (
        source_system_code, source_record_id
    ),
    KEY idx_refund_pay_status_date (biz_date, after_refund_pay_status),
    KEY idx_refund_pay_status_time (refund_pay_detail_id, event_time),
    KEY idx_third_party_refund_no (third_party_refund_no),
    CHECK (event_seq_no > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '退款域退款打款状态迁移事件事实';

/* =========================
   DWD 互动域原子事实
   ========================= */

-- 粒度：一行代表购物车内一个SKU发生的一次数量变更事件
CREATE TABLE dwd_interaction_cart_event_di (
    cart_event_id BIGINT UNSIGNED NOT NULL COMMENT '购物车事件业务ID',
    event_no VARCHAR(64) NOT NULL COMMENT '事件流水号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    user_sk BIGINT NOT NULL DEFAULT -1 COMMENT '事件时点用户版本代理键',
    user_id BIGINT UNSIGNED DEFAULT NULL COMMENT '用户业务ID，游客为空',
    device_id VARCHAR(128) NOT NULL COMMENT '设备ID',
    session_id VARCHAR(128) NOT NULL COMMENT '会话ID',
    shop_sk BIGINT NOT NULL DEFAULT -1 COMMENT '事件时点店铺版本代理键',
    shop_id BIGINT UNSIGNED DEFAULT NULL COMMENT '店铺业务ID',
    sku_sk BIGINT NOT NULL COMMENT '事件时点SKU版本代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU业务ID',
    spu_sk BIGINT NOT NULL COMMENT '事件时点SPU版本代理键',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU业务ID',
    category_sk BIGINT NOT NULL COMMENT '事件时点类目版本代理键',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '类目业务ID',
    channel_sk BIGINT NOT NULL DEFAULT -1 COMMENT '渠道代理键',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    cart_event_type VARCHAR(16) NOT NULL COMMENT '事件类型:加入/移除/改量/清空',
    cart_source VARCHAR(32) DEFAULT NULL COMMENT '购物车事件来源',
    sku_qty_delta INT NOT NULL COMMENT '本次商品数量变化量',
    cart_sku_qty_after INT UNSIGNED NOT NULL COMMENT '事件后购物车商品数量',
    sku_unit_price DECIMAL(18, 4) DEFAULT NULL COMMENT '事件时点商品单价',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    event_time DATETIME(6) NOT NULL COMMENT '事件发生时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取事件发生日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (cart_event_id),
    UNIQUE KEY uk_cart_event_no (event_no),
    UNIQUE KEY uk_cart_event_source (source_system_code, source_record_id),
    KEY idx_cart_user_date (user_sk, biz_date),
    KEY idx_cart_session_time (session_id, event_time),
    KEY idx_cart_sku_date (sku_sk, biz_date),
    CHECK (sku_qty_delta <> 0),
    CHECK (sku_unit_price IS NULL OR sku_unit_price >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '互动域购物车数量变更事件事实';

-- 粒度：一行代表用户对一个商品或店铺发生的一次收藏状态变更事件
CREATE TABLE dwd_interaction_favor_event_di (
    favor_event_id BIGINT UNSIGNED NOT NULL COMMENT '收藏事件业务ID',
    event_no VARCHAR(64) NOT NULL COMMENT '事件流水号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    user_sk BIGINT NOT NULL COMMENT '事件时点用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    device_id VARCHAR(128) DEFAULT NULL COMMENT '设备ID',
    session_id VARCHAR(128) DEFAULT NULL COMMENT '会话ID',
    shop_sk BIGINT NOT NULL DEFAULT -1 COMMENT '事件时点店铺版本代理键',
    shop_id BIGINT UNSIGNED DEFAULT NULL COMMENT '店铺业务ID',
    sku_sk BIGINT NOT NULL DEFAULT -1 COMMENT '事件时点SKU版本代理键',
    sku_id BIGINT UNSIGNED DEFAULT NULL COMMENT 'SKU业务ID',
    spu_sk BIGINT NOT NULL DEFAULT -1 COMMENT '事件时点SPU版本代理键',
    spu_id BIGINT UNSIGNED DEFAULT NULL COMMENT 'SPU业务ID',
    channel_sk BIGINT NOT NULL DEFAULT -1 COMMENT '渠道代理键',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    favor_target_type VARCHAR(16) NOT NULL COMMENT '收藏对象类型:商品/店铺',
    favor_event_type VARCHAR(16) NOT NULL COMMENT '事件类型:收藏/取消收藏',
    event_time DATETIME(6) NOT NULL COMMENT '事件发生时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取事件发生日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (favor_event_id),
    UNIQUE KEY uk_favor_event_no (event_no),
    UNIQUE KEY uk_favor_event_source (source_system_code, source_record_id),
    KEY idx_favor_user_date (user_sk, biz_date),
    KEY idx_favor_shop_date (shop_sk, biz_date),
    KEY idx_favor_sku_date (sku_sk, biz_date),
    CHECK (
        (favor_target_type = '商品' AND sku_id IS NOT NULL)
        OR (favor_target_type = '店铺' AND shop_id IS NOT NULL)
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '互动域收藏状态变更事件事实';

/* =========================
   DWD 流量域原子事实
   ========================= */

-- 粒度：一行代表一个客户端会话从开始到结束的会话事实
CREATE TABLE dwd_traffic_session_di (
    session_fact_id BIGINT UNSIGNED NOT NULL COMMENT '会话事实业务ID',
    session_id VARCHAR(128) NOT NULL COMMENT '会话ID',
    session_date_key INT UNSIGNED NOT NULL COMMENT '会话开始日期键',
    user_sk BIGINT NOT NULL DEFAULT -1 COMMENT '会话开始时用户版本代理键',
    user_id BIGINT UNSIGNED DEFAULT NULL COMMENT '用户业务ID，游客为空',
    device_id VARCHAR(128) NOT NULL COMMENT '设备ID',
    channel_sk BIGINT NOT NULL DEFAULT -1 COMMENT '渠道代理键',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    entry_page_sk BIGINT NOT NULL DEFAULT -1 COMMENT '入口页面代理键',
    entry_page_id VARCHAR(64) DEFAULT NULL COMMENT '入口页面业务ID',
    exit_page_sk BIGINT NOT NULL DEFAULT -1 COMMENT '退出页面代理键',
    exit_page_id VARCHAR(64) DEFAULT NULL COMMENT '退出页面业务ID',
    region_sk BIGINT NOT NULL DEFAULT -1 COMMENT '会话区域版本代理键',
    region_code VARCHAR(20) DEFAULT NULL COMMENT '会话区域编码',
    client_type VARCHAR(32) DEFAULT NULL COMMENT '客户端类型',
    app_version VARCHAR(32) DEFAULT NULL COMMENT '应用版本',
    os_type VARCHAR(32) DEFAULT NULL COMMENT '操作系统',
    ip_masked VARCHAR(64) DEFAULT NULL COMMENT '访问IP脱敏值',
    page_view_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '页面访问次数',
    search_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '搜索次数',
    session_duration_sec INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '会话持续秒数',
    is_bounce TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否跳出会话:0否 1是',
    session_start_time DATETIME(6) NOT NULL COMMENT '会话开始时间',
    session_end_time DATETIME(6) NOT NULL COMMENT '会话结束时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取会话开始日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (session_fact_id),
    UNIQUE KEY uk_session_id (session_id),
    UNIQUE KEY uk_session_source (source_system_code, source_record_id),
    KEY idx_session_user_date (user_sk, biz_date),
    KEY idx_session_channel_date (channel_sk, biz_date),
    KEY idx_session_start_time (session_start_time),
    CHECK (session_start_time <= session_end_time),
    CHECK (is_bounce IN (0, 1)),
    CHECK (is_bounce = 0 OR page_view_count <= 1)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '流量域客户端会话事实';

-- 粒度：一行代表客户端加载一个页面产生的一次页面访问事件
CREATE TABLE dwd_traffic_page_view_di (
    page_view_id BIGINT UNSIGNED NOT NULL COMMENT '页面访问事件业务ID',
    event_no VARCHAR(64) NOT NULL COMMENT '事件流水号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    user_sk BIGINT NOT NULL DEFAULT -1 COMMENT '事件时点用户版本代理键',
    user_id BIGINT UNSIGNED DEFAULT NULL COMMENT '用户业务ID，游客为空',
    device_id VARCHAR(128) NOT NULL COMMENT '设备ID',
    session_id VARCHAR(128) NOT NULL COMMENT '会话ID',
    page_sk BIGINT NOT NULL COMMENT '页面代理键',
    page_id VARCHAR(64) NOT NULL COMMENT '页面业务ID',
    last_page_sk BIGINT NOT NULL DEFAULT -1 COMMENT '上一个页面代理键',
    last_page_id VARCHAR(64) DEFAULT NULL COMMENT '上一个页面业务ID',
    channel_sk BIGINT NOT NULL DEFAULT -1 COMMENT '渠道代理键',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    shop_sk BIGINT NOT NULL DEFAULT -1 COMMENT '关联店铺版本代理键',
    shop_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联店铺业务ID',
    sku_sk BIGINT NOT NULL DEFAULT -1 COMMENT '关联SKU版本代理键',
    sku_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联SKU业务ID',
    spu_sk BIGINT NOT NULL DEFAULT -1 COMMENT '关联SPU版本代理键',
    spu_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联SPU业务ID',
    category_sk BIGINT NOT NULL DEFAULT -1 COMMENT '关联类目版本代理键',
    category_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联类目业务ID',
    promotion_version_sk BIGINT NOT NULL DEFAULT -1 COMMENT '关联促销规则版本代理键',
    promotion_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联活动业务ID',
    search_detail_id BIGINT UNSIGNED DEFAULT NULL COMMENT '来源搜索请求业务ID',
    business_type VARCHAR(32) DEFAULT NULL COMMENT '其他关联业务对象类型',
    business_id VARCHAR(64) DEFAULT NULL COMMENT '其他关联业务对象ID',
    client_type VARCHAR(32) DEFAULT NULL COMMENT '客户端类型',
    app_version VARCHAR(32) DEFAULT NULL COMMENT '应用版本',
    os_type VARCHAR(32) DEFAULT NULL COMMENT '操作系统',
    region_sk BIGINT NOT NULL DEFAULT -1 COMMENT '访问区域版本代理键',
    region_code VARCHAR(20) DEFAULT NULL COMMENT '访问区域编码',
    stay_duration_sec INT UNSIGNED DEFAULT NULL COMMENT '页面停留秒数',
    event_time DATETIME(6) NOT NULL COMMENT '页面加载时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取页面加载日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (page_view_id),
    UNIQUE KEY uk_page_view_event_no (event_no),
    UNIQUE KEY uk_page_view_source (source_system_code, source_record_id),
    KEY idx_page_view_session_time (session_id, event_time),
    KEY idx_page_view_user_date (user_sk, biz_date),
    KEY idx_page_view_page_date (page_sk, biz_date),
    KEY idx_page_view_sku_date (sku_sk, biz_date),
    KEY idx_page_view_promotion_date (promotion_version_sk, biz_date),
    KEY idx_page_view_search (search_detail_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '流量域页面访问事件事实';

-- 粒度：一行代表用户或游客发起的一次搜索请求
CREATE TABLE dwd_traffic_search_di (
    search_detail_id BIGINT UNSIGNED NOT NULL COMMENT '搜索请求业务ID',
    event_no VARCHAR(64) NOT NULL COMMENT '事件流水号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '事件日期键',
    user_sk BIGINT NOT NULL DEFAULT -1 COMMENT '事件时点用户版本代理键',
    user_id BIGINT UNSIGNED DEFAULT NULL COMMENT '用户业务ID，游客为空',
    device_id VARCHAR(128) NOT NULL COMMENT '设备ID',
    session_id VARCHAR(128) NOT NULL COMMENT '会话ID',
    channel_sk BIGINT NOT NULL DEFAULT -1 COMMENT '渠道代理键',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    search_keyword VARCHAR(256) NOT NULL COMMENT '搜索词',
    normalized_keyword VARCHAR(256) DEFAULT NULL COMMENT '归一化搜索词',
    search_source VARCHAR(32) DEFAULT NULL COMMENT '搜索入口',
    result_total_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '搜索结果总数',
    is_no_result TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否无结果:0否 1是',
    is_search_success TINYINT UNSIGNED NOT NULL DEFAULT 1
    COMMENT '请求是否成功:0否 1是',
    event_time DATETIME(6) NOT NULL COMMENT '搜索请求时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取搜索请求日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (search_detail_id),
    UNIQUE KEY uk_search_event_no (event_no),
    UNIQUE KEY uk_search_source_record (source_system_code, source_record_id),
    KEY idx_search_session_time (session_id, event_time),
    KEY idx_search_user_date (user_sk, biz_date),
    KEY idx_search_keyword_date (normalized_keyword, biz_date),
    CHECK (is_no_result IN (0, 1)),
    CHECK (is_search_success IN (0, 1)),
    CHECK (is_no_result = 0 OR result_total_count = 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '流量域搜索请求事件事实';

-- 粒度：一行代表一次搜索请求后点击一个搜索结果的事件
CREATE TABLE dwd_traffic_search_click_di (
    search_click_id BIGINT UNSIGNED NOT NULL COMMENT '搜索点击事件业务ID',
    search_detail_id BIGINT UNSIGNED NOT NULL COMMENT '搜索请求业务ID',
    event_no VARCHAR(64) NOT NULL COMMENT '点击事件流水号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '点击日期键',
    user_sk BIGINT NOT NULL DEFAULT -1 COMMENT '点击时用户版本代理键',
    user_id BIGINT UNSIGNED DEFAULT NULL COMMENT '用户业务ID，游客为空',
    device_id VARCHAR(128) NOT NULL COMMENT '设备ID',
    session_id VARCHAR(128) NOT NULL COMMENT '会话ID',
    channel_sk BIGINT NOT NULL DEFAULT -1 COMMENT '渠道代理键',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    click_sku_sk BIGINT NOT NULL COMMENT '点击时SKU版本代理键',
    click_sku_id BIGINT UNSIGNED NOT NULL COMMENT '点击SKU业务ID',
    click_spu_sk BIGINT NOT NULL COMMENT '点击时SPU版本代理键',
    click_spu_id BIGINT UNSIGNED NOT NULL COMMENT '点击SPU业务ID',
    click_shop_sk BIGINT NOT NULL COMMENT '点击时店铺版本代理键',
    click_shop_id BIGINT UNSIGNED NOT NULL COMMENT '点击店铺业务ID',
    click_category_sk BIGINT NOT NULL COMMENT '点击时类目版本代理键',
    click_category_id BIGINT UNSIGNED NOT NULL COMMENT '点击类目业务ID',
    click_rank INT UNSIGNED NOT NULL COMMENT '点击结果位次',
    event_time DATETIME(6) NOT NULL COMMENT '点击时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取点击日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (search_click_id),
    UNIQUE KEY uk_search_click_event_no (event_no),
    UNIQUE KEY uk_search_click_source (source_system_code, source_record_id),
    KEY idx_search_click_request_time (search_detail_id, event_time),
    KEY idx_search_click_user_date (user_sk, biz_date),
    KEY idx_search_click_sku_date (click_sku_sk, biz_date),
    CHECK (click_rank > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '流量域搜索结果点击事件事实';

/* =========================
   DWD 服务域原子事实
   ========================= */

-- 粒度：一行代表用户对一个订单明细发布的一次初评或追评内容事件
CREATE TABLE dwd_service_comment_detail_di (
    comment_detail_id BIGINT UNSIGNED NOT NULL COMMENT '评价内容事件业务ID',
    comment_id BIGINT UNSIGNED NOT NULL COMMENT '评价主题业务ID',
    parent_comment_detail_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联初评内容事件ID',
    comment_type VARCHAR(16) NOT NULL COMMENT '评价类型:初评/追评',
    comment_date_key INT UNSIGNED NOT NULL COMMENT '评价日期键',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单业务ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细业务ID',
    user_sk BIGINT NOT NULL COMMENT '评价时用户版本代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    shop_sk BIGINT NOT NULL COMMENT '评价时店铺版本代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    sku_sk BIGINT NOT NULL COMMENT '评价时SKU版本代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU业务ID',
    spu_sk BIGINT NOT NULL COMMENT '评价时SPU版本代理键',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU业务ID',
    category_sk BIGINT NOT NULL COMMENT '评价时类目版本代理键',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '类目业务ID',
    comment_level TINYINT UNSIGNED DEFAULT NULL COMMENT '综合评分，追评可为空',
    is_anonymous TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '是否匿名:0否 1是',
    image_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '图片数量',
    video_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '视频数量',
    comment_content VARCHAR(2000) DEFAULT NULL COMMENT '评价内容脱敏值',
    service_score TINYINT UNSIGNED DEFAULT NULL COMMENT '服务评分',
    logistics_score TINYINT UNSIGNED DEFAULT NULL COMMENT '物流评分',
    description_score TINYINT UNSIGNED DEFAULT NULL COMMENT '描述评分',
    sensitive_tag VARCHAR(128) DEFAULT NULL COMMENT '敏感标签',
    sentiment VARCHAR(16) DEFAULT NULL COMMENT '情感分析结果',
    comment_time DATETIME(6) NOT NULL COMMENT '评价发布时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取评价发布日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (comment_detail_id),
    UNIQUE KEY uk_comment_source (source_system_code, source_record_id),
    KEY idx_comment_topic_time (comment_id, comment_time),
    KEY idx_comment_order_detail (order_id, order_detail_id),
    KEY idx_comment_shop_date (shop_sk, biz_date),
    KEY idx_comment_sku_date (sku_sk, biz_date),
    CHECK (comment_level IS NULL OR comment_level BETWEEN 1 AND 5),
    CHECK (service_score IS NULL OR service_score BETWEEN 1 AND 5),
    CHECK (logistics_score IS NULL OR logistics_score BETWEEN 1 AND 5),
    CHECK (description_score IS NULL OR description_score BETWEEN 1 AND 5),
    CHECK (is_anonymous IN (0, 1)),
    CHECK (
        (comment_type = '初评' AND parent_comment_detail_id IS NULL)
        OR (comment_type = '追评' AND parent_comment_detail_id IS NOT NULL)
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '服务域评价内容事件事实';

/* =========================
   DWD 库存域原子事实与周期快照
   ========================= */

-- 粒度：一行代表一个SKU在一个仓库发生的一次库存数量变更事件
CREATE TABLE dwd_inventory_change_di (
    inventory_change_id BIGINT UNSIGNED NOT NULL COMMENT '库存变更事件业务ID',
    change_no VARCHAR(64) NOT NULL COMMENT '库存变更流水号',
    event_date_key INT UNSIGNED NOT NULL COMMENT '变更日期键',
    warehouse_sk BIGINT NOT NULL COMMENT '变更时仓库版本代理键',
    warehouse_id BIGINT UNSIGNED NOT NULL COMMENT '仓库业务ID',
    sku_sk BIGINT NOT NULL COMMENT '变更时SKU版本代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU业务ID',
    spu_sk BIGINT NOT NULL COMMENT '变更时SPU版本代理键',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU业务ID',
    shop_sk BIGINT NOT NULL COMMENT '变更时店铺版本代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    change_type VARCHAR(32) NOT NULL COMMENT '库存变更类型',
    biz_type VARCHAR(32) NOT NULL COMMENT '关联业务类型',
    biz_id VARCHAR(64) NOT NULL COMMENT '关联业务单据ID',
    before_on_hand_qty INT NOT NULL COMMENT '变更前在手库存',
    on_hand_qty_delta INT NOT NULL DEFAULT 0 COMMENT '在手库存变化量',
    after_on_hand_qty INT NOT NULL COMMENT '变更后在手库存',
    before_reserved_qty INT NOT NULL COMMENT '变更前预占库存',
    reserved_qty_delta INT NOT NULL DEFAULT 0 COMMENT '预占库存变化量',
    after_reserved_qty INT NOT NULL COMMENT '变更后预占库存',
    unit_cost DECIMAL(18, 4) DEFAULT NULL COMMENT '变更时单位成本',
    total_cost_delta DECIMAL(18, 4) DEFAULT NULL COMMENT '库存成本变化金额',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    operator_id VARCHAR(64) DEFAULT NULL COMMENT '操作人业务ID',
    operator_type VARCHAR(32) DEFAULT NULL COMMENT '操作人类型',
    remark VARCHAR(512) DEFAULT NULL COMMENT '变更说明',
    event_time DATETIME(6) NOT NULL COMMENT '库存变更时间',
    biz_date DATE NOT NULL COMMENT '业务日期，取库存变更日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源事件唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (inventory_change_id),
    UNIQUE KEY uk_inventory_change_no (change_no),
    UNIQUE KEY uk_inventory_change_source (
        source_system_code, source_record_id
    ),
    KEY idx_inventory_warehouse_sku_time (warehouse_sk, sku_sk, event_time),
    KEY idx_inventory_sku_date (sku_sk, biz_date),
    KEY idx_inventory_biz (biz_type, biz_id),
    CHECK (after_on_hand_qty = before_on_hand_qty + on_hand_qty_delta),
    CHECK (after_reserved_qty = before_reserved_qty + reserved_qty_delta),
    CHECK (before_on_hand_qty >= 0),
    CHECK (after_on_hand_qty >= 0),
    CHECK (before_reserved_qty >= 0),
    CHECK (after_reserved_qty >= 0),
    CHECK (after_reserved_qty <= after_on_hand_qty),
    CHECK (on_hand_qty_delta <> 0 OR reserved_qty_delta <> 0),
    CHECK (unit_cost IS NULL OR unit_cost >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '库存域库存数量变更事件事实';

-- 粒度：一行代表一个SKU在一个仓库一个自然日结束时的库存状态
CREATE TABLE dwd_inventory_daily_snapshot_df (
    snapshot_date_key INT UNSIGNED NOT NULL COMMENT '快照日期键',
    warehouse_sk BIGINT NOT NULL COMMENT '快照时仓库版本代理键',
    warehouse_id BIGINT UNSIGNED NOT NULL COMMENT '仓库业务ID',
    sku_sk BIGINT NOT NULL COMMENT '快照时SKU版本代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU业务ID',
    spu_sk BIGINT NOT NULL COMMENT '快照时SPU版本代理键',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU业务ID',
    shop_sk BIGINT NOT NULL COMMENT '快照时店铺版本代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺业务ID',
    on_hand_qty INT UNSIGNED NOT NULL COMMENT '期末在手库存',
    reserved_qty INT UNSIGNED NOT NULL COMMENT '期末预占库存',
    available_qty INT UNSIGNED NOT NULL COMMENT '期末可用库存',
    in_transit_qty INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '期末在途库存',
    unit_cost DECIMAL(18, 4) DEFAULT NULL COMMENT '期末单位成本',
    inventory_cost_amount DECIMAL(18, 4) DEFAULT NULL COMMENT '期末库存成本金额',
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY' COMMENT '币种编码',
    snapshot_time DATETIME(6) NOT NULL COMMENT '快照时点',
    biz_date DATE NOT NULL COMMENT '业务日期，取快照日期',
    source_system_code VARCHAR(32) NOT NULL COMMENT '来源系统编码',
    source_record_id VARCHAR(128) NOT NULL COMMENT '源记录唯一标识',
    load_batch_id VARCHAR(64) NOT NULL COMMENT '装载批次ID',
    dw_load_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(
        6
    ) COMMENT '入仓时间',
    PRIMARY KEY (snapshot_date_key, warehouse_sk, sku_sk),
    UNIQUE KEY uk_inventory_snapshot_source (
        source_system_code, source_record_id
    ),
    KEY idx_inventory_snapshot_sku_date (sku_sk, snapshot_date_key),
    KEY idx_inventory_snapshot_shop_date (shop_sk, snapshot_date_key),
    CHECK (available_qty = on_hand_qty - reserved_qty),
    CHECK (reserved_qty <= on_hand_qty),
    CHECK (unit_cost IS NULL OR unit_cost >= 0),
    CHECK (inventory_cost_amount IS NULL OR inventory_cost_amount >= 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '库存域SKU仓库每日库存周期快照事实';

/* =========================
   跨表数据质量契约
   ========================= */

-- 1) 事实中的业务日期必须与对应角色日期键映射到同一自然日
-- 2) SCD2代理键必须命中事件时点版本，Type 1代理键必须命中当前成员
-- 3) 同一业务键的拉链版本时间区间不得重叠且最多只能有一个当前版本
-- 4) 规则版本代理键必须命中业务发生时实际执行的不可变规则版本
-- 5) 同一业务对象的规则版本生效区间不得重叠
-- 6) SKU价格变更事件必须按生效时间首尾衔接且前值等于上一事件后值
-- 7) 订单活动分摊金额之和必须等于订单明细活动优惠金额
-- 8) 订单优惠券分摊金额之和必须等于订单明细优惠券优惠金额
-- 9) 支付明细分摊金额之和必须等于支付尝试请求金额
-- 10) 包裹商品分摊重量和运费之和必须分别等于包裹头重量和运费
-- 11) 退款累计成功金额不得超过对应订单明细累计实付金额
-- 12) 库存变更事件必须按仓库和SKU顺序首尾衔接
-- 13) 每日库存快照必须等于当日最后一次库存变更后的状态
