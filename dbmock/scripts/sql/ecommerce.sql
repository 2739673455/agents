-- 电商数仓 DIM 与 DWD 建表脚本
-- 说明：
-- 1) DIM 独立维护一致性维度，DWD 按业务过程保存原子事实
-- 2) _zip 表示拉链维度，_df 表示每日全量快照，_di 表示每日增量明细
-- 3) DWD 保留维度业务键，历史属性按事实时间关联 DIM 生效区间
-- 4) DWD 状态变化统一建模为事件，不在原子事实中覆盖历史状态
-- 5) 所有金额单位为元，业务时间为 DATETIME，数据日期为 DATE
-- 6) DIM 使用代理键，DWD 使用业务事件键作为主键

/* =========================
   DIM 一致性维度
   ========================= */

DROP TABLE IF EXISTS dim_user_info_zip;
CREATE TABLE dim_user_info_zip (
    user_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户维度代理键',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户业务ID',
    user_name VARCHAR(64) DEFAULT NULL COMMENT '用户名',
    nick_name VARCHAR(64) DEFAULT NULL COMMENT '昵称',
    gender VARCHAR(8) DEFAULT '未知' COMMENT '性别:未知/男/女',
    birthday DATE DEFAULT NULL COMMENT '生日',
    phone VARCHAR(20) DEFAULT NULL COMMENT '手机号(脱敏)',
    email VARCHAR(128) DEFAULT NULL COMMENT '邮箱(脱敏)',
    register_time DATETIME DEFAULT NULL COMMENT '注册时间',
    register_channel_code VARCHAR(32) DEFAULT NULL COMMENT '注册渠道编码',
    register_source VARCHAR(32) DEFAULT NULL COMMENT '注册来源(APP/H5/PC等)',
    user_level VARCHAR(16) DEFAULT '1' COMMENT '会员等级',
    user_tag VARCHAR(128) DEFAULT NULL COMMENT '用户标签',
    is_vip TINYINT DEFAULT 0 COMMENT '是否VIP:0否 1是',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '省编码',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '市编码',
    district_code VARCHAR(20) DEFAULT NULL COMMENT '区编码',
    occupation VARCHAR(64) DEFAULT NULL COMMENT '职业',
    income_level VARCHAR(32) DEFAULT NULL COMMENT '收入等级',
    education_level VARCHAR(32) DEFAULT NULL COMMENT '学历等级',
    marital_status VARCHAR(16) DEFAULT NULL COMMENT '婚姻状态',
    user_status VARCHAR(16) DEFAULT '正常' COMMENT '状态:正常/禁用/注销',
    start_date DATE NOT NULL COMMENT '生效开始日期',
    end_date DATE NOT NULL COMMENT '生效结束日期',
    is_current TINYINT DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    PRIMARY KEY (user_sk),
    UNIQUE KEY uk_user_start (user_id, start_date),
    KEY idx_user_current (user_id, is_current),
    KEY idx_province_city (province_code, city_code),
    KEY idx_register_time (register_time)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '用户维度拉链表';

DROP TABLE IF EXISTS dim_shop_info_zip;
CREATE TABLE dim_shop_info_zip (
    shop_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '店铺维度代理键',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺ID',
    start_date DATE NOT NULL COMMENT '生效开始日期',
    end_date DATE NOT NULL COMMENT '生效结束日期',
    shop_name VARCHAR(128) NOT NULL COMMENT '店铺名称',
    shop_type VARCHAR(16) DEFAULT '普通店' COMMENT '店铺类型:自营/旗舰店/专卖店/普通店',
    seller_id BIGINT UNSIGNED DEFAULT NULL COMMENT '商家ID',
    seller_name VARCHAR(128) DEFAULT NULL COMMENT '商家名称',
    industry_type VARCHAR(64) DEFAULT NULL COMMENT '行业类型',
    service_score DECIMAL(4, 2) DEFAULT NULL COMMENT '服务评分',
    logistics_score DECIMAL(4, 2) DEFAULT NULL COMMENT '物流评分',
    description_score DECIMAL(4, 2) DEFAULT NULL COMMENT '描述评分',
    open_time DATETIME DEFAULT NULL COMMENT '开店时间',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '店铺省编码',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '店铺市编码',
    district_code VARCHAR(20) DEFAULT NULL COMMENT '店铺区编码',
    is_self_operated TINYINT DEFAULT 0 COMMENT '是否自营:0否 1是',
    is_global TINYINT DEFAULT 0 COMMENT '是否跨境:0否 1是',
    is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除:0否 1是',
    shop_status VARCHAR(16) DEFAULT '营业' COMMENT '状态:关店/营业',
    is_current TINYINT DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    PRIMARY KEY (shop_sk),
    UNIQUE KEY uk_shop_start (shop_id, start_date),
    KEY idx_seller_id (seller_id),
    KEY idx_shop_type (shop_type),
    KEY idx_shop_current (shop_id, is_current)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '店铺维度拉链表';

DROP TABLE IF EXISTS dim_category_info_zip;
CREATE TABLE dim_category_info_zip (
    category_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '类目维度代理键',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '类目ID',
    start_date DATE NOT NULL COMMENT '生效开始日期',
    end_date DATE NOT NULL COMMENT '生效结束日期',
    category_name VARCHAR(128) NOT NULL COMMENT '类目名称',
    category_level VARCHAR(16) NOT NULL COMMENT '层级:一级/二级/三级',
    parent_category_id BIGINT UNSIGNED DEFAULT NULL COMMENT '父类目ID',
    parent_category_name VARCHAR(128) DEFAULT NULL COMMENT '父类目名称',
    root_category_id BIGINT UNSIGNED DEFAULT NULL COMMENT '一级类目ID',
    root_category_name VARCHAR(128) DEFAULT NULL COMMENT '一级类目名称',
    is_leaf TINYINT DEFAULT 0 COMMENT '是否叶子节点:0否 1是',
    sort_order INT DEFAULT 0 COMMENT '排序',
    category_path VARCHAR(512) DEFAULT NULL COMMENT '类目路径',
    status TINYINT DEFAULT 1 COMMENT '状态:0禁用 1启用',
    is_current TINYINT DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    PRIMARY KEY (category_sk),
    UNIQUE KEY uk_category_start (category_id, start_date),
    KEY idx_parent_id (parent_category_id),
    KEY idx_root_id (root_category_id),
    KEY idx_category_current (category_id, is_current)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '类目维度拉链表';

DROP TABLE IF EXISTS dim_brand_info_zip;
CREATE TABLE dim_brand_info_zip (
    brand_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '品牌维度代理键',
    brand_id BIGINT UNSIGNED NOT NULL COMMENT '品牌ID',
    start_date DATE NOT NULL COMMENT '生效开始日期',
    end_date DATE NOT NULL COMMENT '生效结束日期',
    brand_name VARCHAR(128) NOT NULL COMMENT '品牌名称',
    brand_name_en VARCHAR(128) DEFAULT NULL COMMENT '品牌英文名',
    brand_alias VARCHAR(128) DEFAULT NULL COMMENT '品牌别名',
    brand_logo_url VARCHAR(512) DEFAULT NULL COMMENT '品牌Logo地址',
    brand_story VARCHAR(1024) DEFAULT NULL COMMENT '品牌故事',
    country_code VARCHAR(8) DEFAULT NULL COMMENT '国家编码',
    country_name VARCHAR(64) DEFAULT NULL COMMENT '国家名称',
    first_letter CHAR(1) DEFAULT NULL COMMENT '首字母',
    status TINYINT DEFAULT 1 COMMENT '状态:1有效 0失效',
    is_current TINYINT DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    PRIMARY KEY (brand_sk),
    UNIQUE KEY uk_brand_start (brand_id, start_date),
    KEY idx_brand_name (brand_name),
    KEY idx_country (country_code),
    KEY idx_first_letter (first_letter),
    KEY idx_brand_current (brand_id, is_current)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '品牌维度拉链表';

DROP TABLE IF EXISTS dim_payment_type_zip;
CREATE TABLE dim_payment_type_zip (
    payment_type_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '支付方式维度代理键',
    payment_type_code VARCHAR(32) NOT NULL COMMENT '支付方式编码',
    start_date DATE NOT NULL COMMENT '生效开始日期',
    end_date DATE NOT NULL COMMENT '生效结束日期',
    payment_type_name VARCHAR(64) NOT NULL COMMENT '支付方式名称',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '支付渠道编码',
    channel_name VARCHAR(64) DEFAULT NULL COMMENT '支付渠道名称',
    is_online TINYINT DEFAULT 1 COMMENT '是否线上支付',
    is_installment TINYINT DEFAULT 0 COMMENT '是否分期支付',
    fee_rate DECIMAL(8, 6) DEFAULT NULL COMMENT '支付手续费率',
    status TINYINT DEFAULT 1 COMMENT '状态:1有效 0失效',
    is_current TINYINT DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    PRIMARY KEY (payment_type_sk),
    UNIQUE KEY uk_payment_type_start (payment_type_code, start_date),
    KEY idx_payment_type_current (payment_type_code, is_current)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '支付方式维度拉链表';

DROP TABLE IF EXISTS dim_logistics_company_zip;
CREATE TABLE dim_logistics_company_zip (
    logistics_company_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '物流公司维度代理键',
    logistics_company_id BIGINT UNSIGNED NOT NULL COMMENT '物流公司ID',
    start_date DATE NOT NULL COMMENT '生效开始日期',
    end_date DATE NOT NULL COMMENT '生效结束日期',
    logistics_company_code VARCHAR(32) NOT NULL COMMENT '物流公司编码',
    logistics_company_name VARCHAR(128) NOT NULL COMMENT '物流公司名称',
    logistics_type VARCHAR(32) DEFAULT NULL COMMENT '物流类型:快递/同城/冷链/国际',
    service_phone VARCHAR(32) DEFAULT NULL COMMENT '客服电话',
    is_trace_supported TINYINT DEFAULT 1 COMMENT '是否支持轨迹查询',
    status TINYINT DEFAULT 1 COMMENT '状态:1有效 0失效',
    is_current TINYINT DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    PRIMARY KEY (logistics_company_sk),
    UNIQUE KEY uk_logistics_start (logistics_company_id, start_date),
    KEY idx_company_code (logistics_company_code),
    KEY idx_logistics_current (logistics_company_id, is_current)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '物流公司维度拉链表';

DROP TABLE IF EXISTS dim_geo_region_zip;
CREATE TABLE dim_geo_region_zip (
    region_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '行政区域维度代理键',
    region_code VARCHAR(20) NOT NULL COMMENT '区域编码',
    start_date DATE NOT NULL COMMENT '生效开始日期',
    end_date DATE NOT NULL COMMENT '生效结束日期',
    region_name VARCHAR(128) NOT NULL COMMENT '区域名称',
    region_level TINYINT NOT NULL COMMENT '级别:1省 2市 3区县 4街道',
    parent_region_code VARCHAR(20) DEFAULT NULL COMMENT '父级区域编码',
    parent_region_name VARCHAR(128) DEFAULT NULL COMMENT '父级区域名称',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '省编码',
    province_name VARCHAR(128) DEFAULT NULL COMMENT '省名称',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '市编码',
    city_name VARCHAR(128) DEFAULT NULL COMMENT '市名称',
    district_code VARCHAR(20) DEFAULT NULL COMMENT '区县编码',
    district_name VARCHAR(128) DEFAULT NULL COMMENT '区县名称',
    zip_code VARCHAR(16) DEFAULT NULL COMMENT '邮编',
    status TINYINT DEFAULT 1 COMMENT '状态:1有效 0失效',
    is_current TINYINT DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    PRIMARY KEY (region_sk),
    UNIQUE KEY uk_region_start (region_code, start_date),
    KEY idx_parent_region (parent_region_code),
    KEY idx_province_city (province_code, city_code),
    KEY idx_region_current (region_code, is_current)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '行政区域维度拉链表';

DROP TABLE IF EXISTS dim_spu_info_zip;
CREATE TABLE dim_spu_info_zip (
    spu_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'SPU维度代理键',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU ID',
    start_date DATE NOT NULL COMMENT '生效开始日期',
    end_date DATE NOT NULL COMMENT '生效结束日期',
    spu_name VARCHAR(256) NOT NULL COMMENT 'SPU名称',
    spu_sub_title VARCHAR(512) DEFAULT NULL COMMENT '副标题',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '三级类目ID',
    brand_id BIGINT UNSIGNED DEFAULT NULL COMMENT '品牌ID',
    brand_name VARCHAR(128) DEFAULT NULL COMMENT '品牌名称',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺ID',
    is_virtual TINYINT DEFAULT 0 COMMENT '是否虚拟商品',
    is_presale TINYINT DEFAULT 0 COMMENT '是否预售',
    presale_start_time DATETIME DEFAULT NULL COMMENT '预售开始时间',
    presale_end_time DATETIME DEFAULT NULL COMMENT '预售结束时间',
    weight DECIMAL(12, 3) DEFAULT 0 COMMENT '重量kg',
    volume DECIMAL(12, 3) DEFAULT 0 COMMENT '体积m3',
    on_shelf_time DATETIME DEFAULT NULL COMMENT '上架时间',
    is_current TINYINT DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    PRIMARY KEY (spu_sk),
    UNIQUE KEY uk_spu_start (spu_id, start_date),
    KEY idx_shop_id (shop_id),
    KEY idx_category_id (category_id),
    KEY idx_brand_id (brand_id),
    KEY idx_spu_current (spu_id, is_current)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'SPU维度拉链表';

DROP TABLE IF EXISTS dim_sku_info_zip;
CREATE TABLE dim_sku_info_zip (
    sku_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'SKU维度代理键',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU ID',
    start_date DATE NOT NULL COMMENT '生效开始日期',
    end_date DATE NOT NULL COMMENT '生效结束日期',
    sku_name VARCHAR(256) NOT NULL COMMENT 'SKU名称',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU ID',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺ID',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '三级类目ID',
    brand_id BIGINT UNSIGNED DEFAULT NULL COMMENT '品牌ID',
    bar_code VARCHAR(64) DEFAULT NULL COMMENT '条码',
    sku_specs_json JSON DEFAULT NULL COMMENT 'SKU规格JSON',
    unit VARCHAR(16) DEFAULT '件' COMMENT '单位',
    origin_price DECIMAL(16, 2) DEFAULT NULL COMMENT '原价',
    sale_price DECIMAL(16, 2) DEFAULT NULL COMMENT '销售价',
    cost_price DECIMAL(16, 2) DEFAULT NULL COMMENT '成本价',
    warning_stock INT DEFAULT 0 COMMENT '预警库存',
    is_hot_sale TINYINT DEFAULT 0 COMMENT '是否热销',
    is_new TINYINT DEFAULT 0 COMMENT '是否新品',
    is_deleted TINYINT DEFAULT 0 COMMENT '逻辑删除',
    is_current TINYINT DEFAULT 1 COMMENT '是否当前版本:0否 1是',
    PRIMARY KEY (sku_sk),
    UNIQUE KEY uk_sku_start (sku_id, start_date),
    KEY idx_spu_id (spu_id),
    KEY idx_shop_id (shop_id),
    KEY idx_category_id (category_id),
    KEY idx_brand_id (brand_id),
    KEY idx_sku_current (sku_id, is_current)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'SKU维度拉链表';

DROP TABLE IF EXISTS dim_promotion_info_df;
CREATE TABLE dim_promotion_info_df (
    promotion_snapshot_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '活动快照代理键',
    promotion_id BIGINT UNSIGNED NOT NULL COMMENT '活动ID',
    promotion_name VARCHAR(256) NOT NULL COMMENT '活动名称',
    promotion_type VARCHAR(32) NOT NULL COMMENT '活动类型:满减/折扣/秒杀/拼团',
    promotion_scene VARCHAR(32) DEFAULT NULL COMMENT '活动场景:商品/店铺/平台',
    promotion_level TINYINT DEFAULT 1 COMMENT '活动优先级(数值越小优先级越高)',
    start_time DATETIME DEFAULT NULL COMMENT '生效开始时间',
    end_time DATETIME DEFAULT NULL COMMENT '生效结束时间',
    rule_desc VARCHAR(1024) DEFAULT NULL COMMENT '规则描述',
    threshold_amount DECIMAL(16, 2) DEFAULT NULL COMMENT '门槛金额',
    discount_amount DECIMAL(16, 2) DEFAULT NULL COMMENT '减免金额',
    discount_rate DECIMAL(8, 4) DEFAULT NULL COMMENT '折扣率',
    max_discount_amount DECIMAL(16, 2) DEFAULT NULL COMMENT '封顶减免',
    sponsor_type TINYINT DEFAULT 1 COMMENT '发起方:1平台 2店铺 3品牌',
    sponsor_id BIGINT UNSIGNED DEFAULT NULL COMMENT '发起方ID',
    etl_date DATE NOT NULL COMMENT '快照日期',
    PRIMARY KEY (promotion_snapshot_sk),
    UNIQUE KEY uk_promotion_etl (promotion_id, etl_date),
    KEY idx_promotion_type (promotion_type),
    KEY idx_time_range (start_time, end_time)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '促销活动维度每日全量快照';

DROP TABLE IF EXISTS dim_coupon_info_df;
CREATE TABLE dim_coupon_info_df (
    coupon_snapshot_sk BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '优惠券快照代理键',
    coupon_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券ID',
    coupon_name VARCHAR(256) NOT NULL COMMENT '优惠券名称',
    coupon_type VARCHAR(32) NOT NULL COMMENT '类型:满减券/折扣券/运费券/品类券',
    coupon_scope_type VARCHAR(32) DEFAULT NULL COMMENT '适用范围:全平台/店铺/SPU/SKU/类目',
    coupon_scope_id BIGINT UNSIGNED DEFAULT NULL COMMENT '适用范围ID',
    threshold_amount DECIMAL(16, 2) DEFAULT NULL COMMENT '使用门槛金额',
    discount_amount DECIMAL(16, 2) DEFAULT NULL COMMENT '减免金额',
    discount_rate DECIMAL(8, 4) DEFAULT NULL COMMENT '折扣率',
    max_discount_amount DECIMAL(16, 2) DEFAULT NULL COMMENT '封顶优惠金额',
    issue_start_time DATETIME DEFAULT NULL COMMENT '发券开始时间',
    issue_end_time DATETIME DEFAULT NULL COMMENT '发券结束时间',
    use_start_time DATETIME DEFAULT NULL COMMENT '可用开始时间',
    use_end_time DATETIME DEFAULT NULL COMMENT '可用结束时间',
    total_issue_cnt BIGINT DEFAULT NULL COMMENT '总发行量',
    etl_date DATE NOT NULL COMMENT '快照日期',
    PRIMARY KEY (coupon_snapshot_sk),
    UNIQUE KEY uk_coupon_etl (coupon_id, etl_date),
    KEY idx_coupon_type (coupon_type),
    KEY idx_use_time (use_start_time, use_end_time)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '优惠券维度每日全量快照';

/* =========================
   DWD 原子事实明细
   ========================= */

-- 粒度：一行代表一个订单明细在下单时产生的不可变交易事实
DROP TABLE IF EXISTS dwd_trade_order_detail_di;
CREATE TABLE dwd_trade_order_detail_di (
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细ID(业务主键)',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    parent_order_id BIGINT UNSIGNED DEFAULT NULL COMMENT '父订单ID(拆单场景)',
    trade_no VARCHAR(64) DEFAULT NULL COMMENT '交易流水号',
    order_no VARCHAR(64) DEFAULT NULL COMMENT '订单编号',
    order_source VARCHAR(32) DEFAULT NULL COMMENT '下单来源:APP/H5/PC/小程序',
    order_scene VARCHAR(32) DEFAULT NULL COMMENT '订单场景:普通/秒杀/拼团/预售',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺ID',
    seller_id BIGINT UNSIGNED DEFAULT NULL COMMENT '商家ID',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU ID',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU ID',
    category_id BIGINT UNSIGNED NOT NULL COMMENT '三级类目ID',
    brand_id BIGINT UNSIGNED DEFAULT NULL COMMENT '品牌ID',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '收货省编码',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '收货市编码',
    district_code VARCHAR(20) DEFAULT NULL COMMENT '收货区编码',
    is_first_order TINYINT DEFAULT 0 COMMENT '是否首单',
    is_cross_border TINYINT DEFAULT 0 COMMENT '是否跨境',
    is_pre_sale TINYINT DEFAULT 0 COMMENT '是否预售',
    is_gift TINYINT DEFAULT 0 COMMENT '是否赠品',
    is_risk_order TINYINT DEFAULT 0 COMMENT '是否风控单',
    sku_num INT NOT NULL COMMENT '购买件数',
    sku_origin_price DECIMAL(16, 2) DEFAULT NULL COMMENT 'SKU原价',
    sku_sale_price DECIMAL(16, 2) DEFAULT NULL COMMENT 'SKU成交单价',
    order_detail_amount DECIMAL(16, 2) NOT NULL COMMENT '明细总金额(不含优惠)',
    activity_discount_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '活动优惠金额',
    coupon_discount_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '优惠券优惠金额',
    points_discount_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '积分抵扣金额',
    freight_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '明细分摊运费',
    tax_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '明细分摊税费',
    payable_amount DECIMAL(16, 2) NOT NULL COMMENT '应付金额',
    cost_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '下单时成本快照金额',
    order_create_time DATETIME NOT NULL COMMENT '下单时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按下单日期)',
    PRIMARY KEY (order_detail_id),
    KEY idx_order_id (order_id),
    KEY idx_user_id (user_id),
    KEY idx_shop_id (shop_id),
    KEY idx_sku_id (sku_id),
    KEY idx_order_create_time (order_create_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-下单事实明细';

-- 粒度：一行代表一个订单发生的一次状态迁移事件
DROP TABLE IF EXISTS dwd_trade_order_status_event_di;
CREATE TABLE dwd_trade_order_status_event_di (
    order_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '订单状态事件ID(业务主键)',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺ID',
    before_order_status VARCHAR(32) DEFAULT NULL COMMENT '变更前订单状态',
    after_order_status VARCHAR(32) NOT NULL COMMENT '变更后订单状态',
    status_event_type VARCHAR(32) NOT NULL COMMENT '状态事件类型:创建/支付/发货/收货/取消/完成',
    status_reason_code VARCHAR(32) DEFAULT NULL COMMENT '状态变更原因编码',
    status_reason_desc VARCHAR(512) DEFAULT NULL COMMENT '状态变更原因描述',
    cancel_stage VARCHAR(32) DEFAULT NULL COMMENT '取消阶段:未支付取消/支付后取消/拒收',
    is_terminal_status TINYINT NOT NULL DEFAULT 0 COMMENT '是否终态:0否 1是',
    operator_id BIGINT UNSIGNED DEFAULT NULL COMMENT '操作人ID',
    operator_type VARCHAR(32) DEFAULT NULL COMMENT '操作人类型:系统/用户/商家',
    event_time DATETIME NOT NULL COMMENT '状态变更时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按状态变更日期)',
    PRIMARY KEY (order_status_event_id),
    KEY idx_order_id (order_id),
    KEY idx_user_id (user_id),
    KEY idx_after_status (after_order_status),
    KEY idx_event_time (event_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-订单状态事件事实';

-- 粒度：一行代表一个订单明细分摊到一个促销活动的优惠事实
DROP TABLE IF EXISTS dwd_trade_order_detail_activity_di;
CREATE TABLE dwd_trade_order_detail_activity_di (
    order_detail_activity_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细活动摊销ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    promotion_id BIGINT UNSIGNED NOT NULL COMMENT '活动ID',
    promotion_type VARCHAR(32) DEFAULT NULL COMMENT '活动类型',
    promotion_level TINYINT DEFAULT NULL COMMENT '活动层级优先级',
    promotion_discount_amount DECIMAL(16, 2) NOT NULL COMMENT '活动分摊金额',
    rule_snapshot VARCHAR(1024) DEFAULT NULL COMMENT '规则快照',
    order_create_time DATETIME NOT NULL COMMENT '下单时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按下单日期)',
    PRIMARY KEY (order_detail_activity_id),
    KEY idx_order_detail_id (order_detail_id),
    KEY idx_promotion_id (promotion_id),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-订单明细活动分摊事实';

-- 粒度：一行代表一个订单明细分摊到一个用户优惠券实例的优惠事实
DROP TABLE IF EXISTS dwd_trade_order_detail_coupon_di;
CREATE TABLE dwd_trade_order_detail_coupon_di (
    order_detail_coupon_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细优惠券摊销ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    coupon_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券ID',
    user_coupon_id BIGINT UNSIGNED NOT NULL COMMENT '用户优惠券实例ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '领券用户ID',
    coupon_type VARCHAR(32) DEFAULT NULL COMMENT '券类型',
    coupon_scope_type VARCHAR(32) DEFAULT NULL COMMENT '券适用范围',
    coupon_discount_amount DECIMAL(16, 2) NOT NULL COMMENT '优惠券分摊金额',
    coupon_batch_no VARCHAR(64) DEFAULT NULL COMMENT '券批次号',
    coupon_receive_time DATETIME DEFAULT NULL COMMENT '领券时间',
    coupon_use_time DATETIME DEFAULT NULL COMMENT '用券时间',
    order_create_time DATETIME NOT NULL COMMENT '下单时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按下单日期)',
    PRIMARY KEY (order_detail_coupon_id),
    KEY idx_order_detail_id (order_detail_id),
    KEY idx_coupon_id (coupon_id),
    KEY idx_user_coupon_id (user_coupon_id),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-订单明细优惠券分摊事实';

-- 粒度：一行代表一次支付请求或支付尝试
DROP TABLE IF EXISTS dwd_trade_pay_detail_di;
CREATE TABLE dwd_trade_pay_detail_di (
    pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '支付明细ID(业务主键)',
    pay_order_no VARCHAR(64) NOT NULL COMMENT '支付单号',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    payment_type_code VARCHAR(32) NOT NULL COMMENT '支付方式编码',
    payment_channel_code VARCHAR(32) DEFAULT NULL COMMENT '支付渠道编码',
    pay_scene VARCHAR(32) DEFAULT NULL COMMENT '支付场景:收银台/自动扣款/合并支付',
    currency_code VARCHAR(8) DEFAULT 'CNY' COMMENT '币种',
    total_pay_amount DECIMAL(16, 2) NOT NULL COMMENT '支付总金额',
    cash_pay_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '现金支付金额',
    coupon_pay_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '券抵扣金额',
    points_pay_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '积分抵扣金额',
    balance_pay_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '余额支付金额',
    installment_cnt INT DEFAULT NULL COMMENT '分期期数',
    installment_fee_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '分期手续费',
    pay_request_time DATETIME NOT NULL COMMENT '支付请求时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按支付请求日期)',
    PRIMARY KEY (pay_detail_id),
    KEY idx_pay_order_no (pay_order_no),
    KEY idx_user_id (user_id),
    KEY idx_payment_type (payment_type_code),
    KEY idx_pay_request_time (pay_request_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-支付请求事实';

-- 粒度：一行代表一笔支付分摊到一个订单明细的金额事实
DROP TABLE IF EXISTS dwd_trade_pay_order_detail_di;
CREATE TABLE dwd_trade_pay_order_detail_di (
    pay_order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '支付订单明细分摊ID(业务主键)',
    pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '支付明细ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细ID',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺ID',
    seller_id BIGINT UNSIGNED DEFAULT NULL COMMENT '商家ID',
    allocated_pay_amount DECIMAL(16, 2) NOT NULL COMMENT '分摊支付总金额',
    allocated_cash_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '分摊现金支付金额',
    allocated_coupon_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '分摊券抵扣金额',
    allocated_points_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '分摊积分抵扣金额',
    allocated_balance_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '分摊余额支付金额',
    etl_date DATE NOT NULL COMMENT '数据日期(按支付请求日期)',
    PRIMARY KEY (pay_order_detail_id),
    KEY idx_pay_detail_id (pay_detail_id),
    KEY idx_order_id (order_id),
    KEY idx_order_detail_id (order_detail_id),
    KEY idx_shop_id (shop_id),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-支付订单明细分摊事实';

-- 粒度：一行代表一次支付状态迁移事件
DROP TABLE IF EXISTS dwd_trade_pay_status_event_di;
CREATE TABLE dwd_trade_pay_status_event_di (
    pay_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '支付状态事件ID(业务主键)',
    pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '支付明细ID',
    pay_order_no VARCHAR(64) NOT NULL COMMENT '支付单号',
    third_party_pay_no VARCHAR(128) DEFAULT NULL COMMENT '第三方支付流水号',
    before_pay_status VARCHAR(32) DEFAULT NULL COMMENT '变更前支付状态',
    after_pay_status VARCHAR(32) NOT NULL COMMENT '变更后支付状态:处理中/成功/失败/关闭',
    pay_fail_reason_code VARCHAR(32) DEFAULT NULL COMMENT '支付失败原因编码',
    pay_fail_reason_desc VARCHAR(512) DEFAULT NULL COMMENT '支付失败原因描述',
    event_time DATETIME NOT NULL COMMENT '状态变更时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按状态变更日期)',
    PRIMARY KEY (pay_status_event_id),
    KEY idx_pay_detail_id (pay_detail_id),
    KEY idx_third_party_pay_no (third_party_pay_no),
    KEY idx_after_status (after_pay_status),
    KEY idx_event_time (event_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-支付状态事件事实';

-- 粒度：一行代表一个正向或退货物流包裹
DROP TABLE IF EXISTS dwd_trade_delivery_di;
CREATE TABLE dwd_trade_delivery_di (
    delivery_id BIGINT UNSIGNED NOT NULL COMMENT '物流包裹ID(业务主键)',
    delivery_no VARCHAR(64) NOT NULL COMMENT '物流单号',
    package_no VARCHAR(64) NOT NULL COMMENT '包裹编号',
    delivery_direction VARCHAR(16) NOT NULL COMMENT '物流方向:正向/退货',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    refund_no VARCHAR(64) DEFAULT NULL COMMENT '关联退款单号',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺ID',
    warehouse_id BIGINT UNSIGNED DEFAULT NULL COMMENT '仓库ID',
    logistics_company_id BIGINT UNSIGNED DEFAULT NULL COMMENT '物流公司ID',
    tracking_no VARCHAR(128) DEFAULT NULL COMMENT '运单号',
    delivery_type VARCHAR(32) DEFAULT NULL COMMENT '配送类型:快递/同城/门店自提',
    receiver_name VARCHAR(64) DEFAULT NULL COMMENT '收件人(脱敏)',
    receiver_phone VARCHAR(20) DEFAULT NULL COMMENT '收件电话(脱敏)',
    receiver_province_code VARCHAR(20) DEFAULT NULL COMMENT '收货省编码',
    receiver_city_code VARCHAR(20) DEFAULT NULL COMMENT '收货市编码',
    receiver_district_code VARCHAR(20) DEFAULT NULL COMMENT '收货区编码',
    receiver_address VARCHAR(512) DEFAULT NULL COMMENT '收货地址(脱敏)',
    package_weight DECIMAL(16, 3) DEFAULT 0 COMMENT '包裹重量kg',
    freight_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '包裹运费金额',
    delivery_create_time DATETIME NOT NULL COMMENT '物流包裹创建时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按包裹创建日期)',
    PRIMARY KEY (delivery_id),
    UNIQUE KEY uk_package_no (package_no),
    KEY idx_delivery_no (delivery_no),
    KEY idx_order_id (order_id),
    KEY idx_refund_no (refund_no),
    KEY idx_tracking_no (tracking_no),
    KEY idx_delivery_create_time (delivery_create_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-物流包裹事实';

-- 粒度：一行代表一个物流包裹中的一个订单明细或退款明细
DROP TABLE IF EXISTS dwd_trade_delivery_item_di;
CREATE TABLE dwd_trade_delivery_item_di (
    delivery_item_id BIGINT UNSIGNED NOT NULL COMMENT '物流包裹商品明细ID(业务主键)',
    delivery_id BIGINT UNSIGNED NOT NULL COMMENT '物流包裹ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细ID',
    refund_detail_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联退款明细ID',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU ID',
    delivery_sku_num INT NOT NULL COMMENT '本包裹商品件数',
    item_weight DECIMAL(16, 3) DEFAULT 0 COMMENT '商品分摊重量kg',
    allocated_freight_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '商品分摊运费金额',
    etl_date DATE NOT NULL COMMENT '数据日期(按包裹创建日期)',
    PRIMARY KEY (delivery_item_id),
    KEY idx_delivery_id (delivery_id),
    KEY idx_order_id (order_id),
    KEY idx_order_detail_id (order_detail_id),
    KEY idx_refund_detail_id (refund_detail_id),
    KEY idx_sku_id (sku_id),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-物流包裹商品明细事实';

-- 粒度：一行代表一个物流包裹发生的一次状态迁移事件
DROP TABLE IF EXISTS dwd_trade_delivery_status_event_di;
CREATE TABLE dwd_trade_delivery_status_event_di (
    delivery_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '物流状态事件ID(业务主键)',
    delivery_id BIGINT UNSIGNED NOT NULL COMMENT '物流包裹ID',
    before_delivery_status VARCHAR(32) DEFAULT NULL COMMENT '变更前物流状态',
    after_delivery_status VARCHAR(32) NOT NULL COMMENT '变更后物流状态:待出库/已出库/运输中/已签收/拒收',
    status_event_code VARCHAR(32) NOT NULL COMMENT '物流状态事件编码',
    event_location VARCHAR(256) DEFAULT NULL COMMENT '物流事件地点',
    event_remark VARCHAR(512) DEFAULT NULL COMMENT '物流事件说明',
    event_time DATETIME NOT NULL COMMENT '物流状态变更时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按状态变更日期)',
    PRIMARY KEY (delivery_status_event_id),
    KEY idx_delivery_id (delivery_id),
    KEY idx_after_status (after_delivery_status),
    KEY idx_event_time (event_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-物流状态事件事实';

-- 粒度：一行代表一个退款申请中的一个订单商品明细
DROP TABLE IF EXISTS dwd_trade_refund_detail_di;
CREATE TABLE dwd_trade_refund_detail_di (
    refund_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款明细ID(业务主键)',
    refund_no VARCHAR(64) NOT NULL COMMENT '退款单号',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺ID',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU ID',
    refund_sku_num INT NOT NULL COMMENT '申请退款商品件数',
    refund_type VARCHAR(32) NOT NULL COMMENT '退款类型:仅退款/退货退款',
    refund_reason_code VARCHAR(32) DEFAULT NULL COMMENT '退款原因编码',
    refund_reason_desc VARCHAR(256) DEFAULT NULL COMMENT '退款原因描述',
    refund_apply_amount DECIMAL(16, 2) NOT NULL COMMENT '申请退款金额',
    is_quality_issue TINYINT DEFAULT 0 COMMENT '是否质量问题',
    need_return_goods TINYINT DEFAULT 0 COMMENT '是否需要退货',
    apply_time DATETIME NOT NULL COMMENT '申请时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按申请日期)',
    PRIMARY KEY (refund_detail_id),
    KEY idx_refund_no (refund_no),
    KEY idx_order_detail_id (order_detail_id),
    KEY idx_user_id (user_id),
    KEY idx_apply_time (apply_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-退款申请商品明细事实';

-- 粒度：一行代表一个退款明细发生的一次状态迁移事件
DROP TABLE IF EXISTS dwd_trade_refund_status_event_di;
CREATE TABLE dwd_trade_refund_status_event_di (
    refund_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '退款状态事件ID(业务主键)',
    refund_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款明细ID',
    refund_no VARCHAR(64) NOT NULL COMMENT '退款单号',
    before_refund_status VARCHAR(32) DEFAULT NULL COMMENT '变更前退款状态',
    after_refund_status VARCHAR(32) NOT NULL COMMENT '变更后退款状态:申请/审核通过/审核拒绝/待退货/退款中/成功/关闭',
    approved_refund_amount DECIMAL(16, 2) DEFAULT NULL COMMENT '本次审核通过退款金额',
    status_reason_code VARCHAR(32) DEFAULT NULL COMMENT '状态变更原因编码',
    status_reason_desc VARCHAR(512) DEFAULT NULL COMMENT '状态变更原因描述',
    operator_id BIGINT UNSIGNED DEFAULT NULL COMMENT '操作人ID',
    operator_type VARCHAR(32) DEFAULT NULL COMMENT '操作人类型:系统/用户/商家/客服',
    event_time DATETIME NOT NULL COMMENT '状态变更时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按状态变更日期)',
    PRIMARY KEY (refund_status_event_id),
    KEY idx_refund_detail_id (refund_detail_id),
    KEY idx_refund_no (refund_no),
    KEY idx_after_status (after_refund_status),
    KEY idx_event_time (event_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-退款状态事件事实';

-- 粒度：一行代表一次退款资金原路退回或账户打款请求
DROP TABLE IF EXISTS dwd_trade_refund_pay_detail_di;
CREATE TABLE dwd_trade_refund_pay_detail_di (
    refund_pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款支付明细ID(业务主键)',
    refund_no VARCHAR(64) NOT NULL COMMENT '退款单号',
    refund_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款明细ID',
    pay_detail_id BIGINT UNSIGNED DEFAULT NULL COMMENT '原支付明细ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    payment_type_code VARCHAR(32) NOT NULL COMMENT '原支付方式编码',
    refund_channel_code VARCHAR(32) DEFAULT NULL COMMENT '退款渠道编码',
    refund_amount DECIMAL(16, 2) NOT NULL COMMENT '退款总金额',
    refund_goods_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '退商品金额',
    refund_freight_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '退运费金额',
    refund_tax_amount DECIMAL(16, 2) DEFAULT 0 COMMENT '退税金额',
    refund_account_type VARCHAR(32) DEFAULT NULL COMMENT '退款账户类型',
    refund_pay_request_time DATETIME NOT NULL COMMENT '退款打款请求时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按退款打款请求日期)',
    PRIMARY KEY (refund_pay_detail_id),
    KEY idx_refund_no (refund_no),
    KEY idx_refund_detail_id (refund_detail_id),
    KEY idx_refund_pay_request_time (refund_pay_request_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-退款打款事实明细';

-- 粒度：一行代表一次退款打款状态迁移事件
DROP TABLE IF EXISTS dwd_trade_refund_pay_status_event_di;
CREATE TABLE dwd_trade_refund_pay_status_event_di (
    refund_pay_status_event_id BIGINT UNSIGNED NOT NULL COMMENT '退款打款状态事件ID(业务主键)',
    refund_pay_detail_id BIGINT UNSIGNED NOT NULL COMMENT '退款支付明细ID',
    third_party_refund_no VARCHAR(128) DEFAULT NULL COMMENT '第三方退款流水号',
    before_refund_pay_status VARCHAR(32) DEFAULT NULL COMMENT '变更前退款打款状态',
    after_refund_pay_status VARCHAR(32) NOT NULL COMMENT '变更后退款打款状态:处理中/成功/失败/关闭',
    refund_fail_reason_code VARCHAR(32) DEFAULT NULL COMMENT '退款失败原因编码',
    refund_fail_reason_desc VARCHAR(512) DEFAULT NULL COMMENT '退款失败原因描述',
    event_time DATETIME NOT NULL COMMENT '状态变更时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按状态变更日期)',
    PRIMARY KEY (refund_pay_status_event_id),
    KEY idx_refund_pay_detail_id (refund_pay_detail_id),
    KEY idx_third_party_refund_no (third_party_refund_no),
    KEY idx_after_status (after_refund_pay_status),
    KEY idx_event_time (event_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '交易域-退款打款状态事件事实';

-- 粒度：一行代表一次用户加购事件
DROP TABLE IF EXISTS dwd_interaction_cart_add_di;
CREATE TABLE dwd_interaction_cart_add_di (
    cart_add_id BIGINT UNSIGNED NOT NULL COMMENT '加购明细ID(业务主键)',
    event_no VARCHAR(64) DEFAULT NULL COMMENT '事件流水号',
    user_id BIGINT UNSIGNED DEFAULT NULL COMMENT '用户ID(游客为空)',
    device_id VARCHAR(128) DEFAULT NULL COMMENT '设备ID',
    session_id VARCHAR(128) DEFAULT NULL COMMENT '会话ID',
    shop_id BIGINT UNSIGNED DEFAULT NULL COMMENT '店铺ID',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU ID',
    spu_id BIGINT UNSIGNED DEFAULT NULL COMMENT 'SPU ID',
    category_id BIGINT UNSIGNED DEFAULT NULL COMMENT '类目ID',
    cart_source VARCHAR(32) DEFAULT NULL COMMENT '加购来源:商品详情/搜索/推荐/活动页',
    client_type VARCHAR(32) DEFAULT NULL COMMENT '客户端类型:iOS/Android/H5/PC/小程序',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    add_sku_num INT NOT NULL COMMENT '加购件数',
    sku_price DECIMAL(16, 2) DEFAULT NULL COMMENT '加购时单价',
    event_time DATETIME NOT NULL COMMENT '加购时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按事件日期)',
    PRIMARY KEY (cart_add_id),
    KEY idx_user_id (user_id),
    KEY idx_sku_id (sku_id),
    KEY idx_event_time (event_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '互动域-加购事实明细';

-- 粒度：一行代表一次用户收藏商品或店铺事件
DROP TABLE IF EXISTS dwd_interaction_favor_add_di;
CREATE TABLE dwd_interaction_favor_add_di (
    favor_add_id BIGINT UNSIGNED NOT NULL COMMENT '收藏明细ID(业务主键)',
    event_no VARCHAR(64) DEFAULT NULL COMMENT '事件流水号',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    shop_id BIGINT UNSIGNED DEFAULT NULL COMMENT '店铺ID',
    sku_id BIGINT UNSIGNED DEFAULT NULL COMMENT 'SKU ID',
    spu_id BIGINT UNSIGNED DEFAULT NULL COMMENT 'SPU ID',
    favor_type VARCHAR(32) NOT NULL COMMENT '收藏类型:商品/店铺',
    client_type VARCHAR(32) DEFAULT NULL COMMENT '客户端类型',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    event_time DATETIME NOT NULL COMMENT '收藏时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按事件日期)',
    PRIMARY KEY (favor_add_id),
    KEY idx_user_id (user_id),
    KEY idx_spu_id (spu_id),
    KEY idx_event_time (event_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '互动域-收藏事实明细';

-- 粒度：一行代表一次页面访问事件
DROP TABLE IF EXISTS dwd_traffic_page_view_di;
CREATE TABLE dwd_traffic_page_view_di (
    page_view_id BIGINT UNSIGNED NOT NULL COMMENT '页面访问明细ID(业务主键)',
    event_no VARCHAR(64) DEFAULT NULL COMMENT '事件流水号',
    user_id BIGINT UNSIGNED DEFAULT NULL COMMENT '用户ID(游客为空)',
    device_id VARCHAR(128) DEFAULT NULL COMMENT '设备ID',
    session_id VARCHAR(128) DEFAULT NULL COMMENT '会话ID',
    page_id VARCHAR(64) NOT NULL COMMENT '页面ID',
    page_name VARCHAR(128) DEFAULT NULL COMMENT '页面名称',
    last_page_id VARCHAR(64) DEFAULT NULL COMMENT '上一个页面ID',
    page_type VARCHAR(32) DEFAULT NULL COMMENT '页面类型:首页/详情/活动/搜索/下单',
    shop_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联店铺ID',
    sku_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联SKU ID',
    spu_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联SPU ID',
    category_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联类目ID',
    promotion_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联活动ID',
    search_detail_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联搜索明细ID',
    business_type VARCHAR(32) DEFAULT NULL COMMENT '其他业务实体类型',
    business_id VARCHAR(64) DEFAULT NULL COMMENT '其他业务实体ID',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    client_type VARCHAR(32) DEFAULT NULL COMMENT '客户端类型',
    app_version VARCHAR(32) DEFAULT NULL COMMENT 'APP版本',
    os_type VARCHAR(32) DEFAULT NULL COMMENT '操作系统',
    ip VARCHAR(64) DEFAULT NULL COMMENT '访问IP(脱敏)',
    province_code VARCHAR(20) DEFAULT NULL COMMENT '访问省编码',
    city_code VARCHAR(20) DEFAULT NULL COMMENT '访问市编码',
    stay_duration_sec INT DEFAULT NULL COMMENT '停留秒数',
    is_bounce TINYINT DEFAULT 0 COMMENT '是否跳出',
    event_time DATETIME NOT NULL COMMENT '访问时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按访问日期)',
    PRIMARY KEY (page_view_id),
    KEY idx_user_id (user_id),
    KEY idx_page_id (page_id),
    KEY idx_sku_id (sku_id),
    KEY idx_promotion_id (promotion_id),
    KEY idx_search_detail_id (search_detail_id),
    KEY idx_business (business_type, business_id),
    KEY idx_event_time (event_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '流量域-页面访问事实明细';

-- 粒度：一行代表一次搜索请求及其返回结果概要
DROP TABLE IF EXISTS dwd_traffic_search_di;
CREATE TABLE dwd_traffic_search_di (
    search_detail_id BIGINT UNSIGNED NOT NULL COMMENT '搜索明细ID(业务主键)',
    event_no VARCHAR(64) DEFAULT NULL COMMENT '事件流水号',
    user_id BIGINT UNSIGNED DEFAULT NULL COMMENT '用户ID(游客为空)',
    device_id VARCHAR(128) DEFAULT NULL COMMENT '设备ID',
    session_id VARCHAR(128) DEFAULT NULL COMMENT '会话ID',
    search_keyword VARCHAR(256) NOT NULL COMMENT '搜索词',
    search_source VARCHAR(32) DEFAULT NULL COMMENT '搜索入口:首页/分类页/店铺页',
    result_total_cnt INT DEFAULT NULL COMMENT '搜索结果总数',
    is_no_result TINYINT DEFAULT 0 COMMENT '是否无结果',
    is_search_success TINYINT DEFAULT 1 COMMENT '是否成功返回结果',
    channel_code VARCHAR(32) DEFAULT NULL COMMENT '渠道编码',
    client_type VARCHAR(32) DEFAULT NULL COMMENT '客户端类型',
    event_time DATETIME NOT NULL COMMENT '搜索时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按搜索日期)',
    PRIMARY KEY (search_detail_id),
    KEY idx_user_id (user_id),
    KEY idx_keyword (search_keyword),
    KEY idx_event_time (event_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '流量域-搜索事实明细';

-- 粒度：一行代表用户在一次搜索请求后点击一个搜索结果的事件
DROP TABLE IF EXISTS dwd_traffic_search_click_di;
CREATE TABLE dwd_traffic_search_click_di (
    search_click_id BIGINT UNSIGNED NOT NULL COMMENT '搜索点击ID(业务主键)',
    search_detail_id BIGINT UNSIGNED NOT NULL COMMENT '搜索明细ID',
    event_no VARCHAR(64) DEFAULT NULL COMMENT '点击事件流水号',
    user_id BIGINT UNSIGNED DEFAULT NULL COMMENT '用户ID(游客为空)',
    device_id VARCHAR(128) DEFAULT NULL COMMENT '设备ID',
    session_id VARCHAR(128) DEFAULT NULL COMMENT '会话ID',
    click_sku_id BIGINT UNSIGNED NOT NULL COMMENT '点击SKU ID',
    click_spu_id BIGINT UNSIGNED DEFAULT NULL COMMENT '点击SPU ID',
    click_shop_id BIGINT UNSIGNED DEFAULT NULL COMMENT '点击店铺ID',
    click_category_id BIGINT UNSIGNED DEFAULT NULL COMMENT '点击类目ID',
    click_rank INT NOT NULL COMMENT '点击结果位次',
    click_time DATETIME NOT NULL COMMENT '点击时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按点击日期)',
    PRIMARY KEY (search_click_id),
    KEY idx_search_detail_id (search_detail_id),
    KEY idx_user_id (user_id),
    KEY idx_click_sku_id (click_sku_id),
    KEY idx_click_time (click_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '流量域-搜索结果点击事实';

-- 粒度：一行代表一次初评或追评内容事件
DROP TABLE IF EXISTS dwd_service_comment_detail_di;
CREATE TABLE dwd_service_comment_detail_di (
    comment_detail_id BIGINT UNSIGNED NOT NULL COMMENT '评价明细ID(业务主键)',
    comment_id BIGINT UNSIGNED NOT NULL COMMENT '评价ID',
    order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID',
    order_detail_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    shop_id BIGINT UNSIGNED NOT NULL COMMENT '店铺ID',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU ID',
    spu_id BIGINT UNSIGNED NOT NULL COMMENT 'SPU ID',
    category_id BIGINT UNSIGNED DEFAULT NULL COMMENT '类目ID',
    comment_level TINYINT NOT NULL COMMENT '评分(1-5)',
    is_anonymous TINYINT DEFAULT 0 COMMENT '是否匿名',
    is_with_image TINYINT DEFAULT 0 COMMENT '是否晒图',
    is_with_video TINYINT DEFAULT 0 COMMENT '是否晒视频',
    is_append_comment TINYINT DEFAULT 0 COMMENT '是否追评',
    comment_content VARCHAR(2000) DEFAULT NULL COMMENT '评价内容(可脱敏)',
    service_score TINYINT DEFAULT NULL COMMENT '服务评分',
    logistics_score TINYINT DEFAULT NULL COMMENT '物流评分',
    description_score TINYINT DEFAULT NULL COMMENT '描述评分',
    sensitive_tag VARCHAR(128) DEFAULT NULL COMMENT '敏感标签',
    sentiment VARCHAR(16) DEFAULT NULL COMMENT '情感分析结果:正向/中性/负向',
    comment_time DATETIME NOT NULL COMMENT '评价时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按评价日期)',
    PRIMARY KEY (comment_detail_id),
    KEY idx_comment_id (comment_id),
    KEY idx_order_detail_id (order_detail_id),
    KEY idx_sku_id (sku_id),
    KEY idx_comment_time (comment_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '服务域-评价事实明细';

-- 粒度：一行代表一个SKU在一个仓库发生的一次库存变更事件
DROP TABLE IF EXISTS dwd_inventory_change_di;
CREATE TABLE dwd_inventory_change_di (
    inventory_change_id BIGINT UNSIGNED NOT NULL COMMENT '库存变更明细ID(业务主键)',
    change_no VARCHAR(64) DEFAULT NULL COMMENT '库存变更流水号',
    sku_id BIGINT UNSIGNED NOT NULL COMMENT 'SKU ID',
    spu_id BIGINT UNSIGNED DEFAULT NULL COMMENT 'SPU ID',
    shop_id BIGINT UNSIGNED DEFAULT NULL COMMENT '店铺ID',
    warehouse_id BIGINT UNSIGNED DEFAULT NULL COMMENT '仓库ID',
    change_type VARCHAR(32) NOT NULL COMMENT '变更类型:入库/出库/锁定/解锁/盘点',
    biz_type VARCHAR(32) DEFAULT NULL COMMENT '业务类型:下单/取消/发货/退款/调拨',
    biz_id VARCHAR(64) DEFAULT NULL COMMENT '业务单据ID',
    before_stock_qty INT NOT NULL COMMENT '变更前库存',
    change_qty INT NOT NULL COMMENT '变更数量(可正可负)',
    after_stock_qty INT NOT NULL COMMENT '变更后库存',
    before_lock_qty INT DEFAULT 0 COMMENT '变更前锁定库存',
    change_lock_qty INT DEFAULT 0 COMMENT '锁定库存变更量',
    after_lock_qty INT DEFAULT 0 COMMENT '变更后锁定库存',
    unit_cost DECIMAL(16, 4) DEFAULT NULL COMMENT '单位成本',
    total_cost_change DECIMAL(16, 4) DEFAULT NULL COMMENT '总成本变动',
    operator_id BIGINT UNSIGNED DEFAULT NULL COMMENT '操作人ID',
    operator_type VARCHAR(32) DEFAULT NULL COMMENT '操作人类型:系统/用户/商家/仓管',
    remark VARCHAR(512) DEFAULT NULL COMMENT '备注',
    change_time DATETIME NOT NULL COMMENT '变更时间',
    etl_date DATE NOT NULL COMMENT '数据日期(按库存变更日期)',
    PRIMARY KEY (inventory_change_id),
    KEY idx_sku_id (sku_id),
    KEY idx_warehouse_id (warehouse_id),
    KEY idx_biz (biz_type, biz_id),
    KEY idx_change_time (change_time),
    KEY idx_etl_date (etl_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '库存域-库存变更事实明细';
