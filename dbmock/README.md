# dbmock

为 `insight` 项目构造一个中国中小型综合电商平台规模的两年期数仓，最终写入 Apache Doris

## 构建目标

- 完整任务的默认终止日期是任务开始执行时的业务日期，不是写死在代码里的某个日期
- 默认开始日期是终止日期向前推两个自然年，开始日期和终止日期均包含在数据范围内
- 任务使用 `Asia/Shanghai` 业务时区，当天的事件时间不会晚于任务实际开始时刻
- 商品、SKU、品牌、店铺、类目和价格来自国内公开电商页面并保留采集血缘
- 用户、订单、营销、库存和行为无法从外部平台取得，按中小型电商的合理分布生成，并保持跨表业务一致性
- 历史事实按业务发生时间生成，来源更新时间、首次入仓时间和最近更新时间按历史处理链路生成，不统一使用任务执行时刻
- 无法从来源确认的字段保留为空，不用随机值伪装成真实采集值

## 当前实现

- 本地 `data` 商品目录已准备完成并通过校验
- 商品目录包含 30,000 个 SPU、120,000 个 SKU、873 个类目、2,382 个品牌和 994 个店铺
- 商品来源为苏宁 22,500 个 SPU、当当 7,500 个 SPU，覆盖 13 个一级类目
- 每个 SPU 包含 1～40 个真实来源 SKU，平均 4 个
- Doris DDL 包含 47 张维度、桥表、原子事实和周期快照表

`data` 目录不进入 Git。新环境克隆项目后需要重新采集，或自行复制已经校验通过的数据目录

## 数据边界

真实采集的数据包括：

- 商品标题、品牌或出版社、店铺、来源类目和商品参数
- SPU 与 SKU 关系、SKU 规格、售价、划线价、图片和来源链接
- 来源平台、外部商品 ID、外部 SKU ID 和采集时间等技术血缘

平台标准化的数据包括：

- 稳定的内部 SPU、SKU、品牌、类目、商家和店铺业务 ID
- 三级类目映射、品牌名称归一和平台店铺类型
- 商品使用 `source_system_code=PIM`
- 商家和店铺使用 `source_system_code=MERCHANT_CENTER`

模拟生成的数据包括用户、标签、仓库、营销、订单、支付、履约、退款、评价、库存和用户行为。这些记录不是外部采集数据，但必须满足真实业务的时间顺序、状态流转、金额分摊、库存连续性和维度引用关系

审计时间按以下口径生成：

- 事实表以事件时间为基础，模拟分钟级处理延迟后写入 `dw_load_time`
- 日快照在快照时点之后模拟小时级离线处理延迟
- 维度表以首次生效时间或来源更新时间为基础生成 `source_update_time`、`dw_load_time` 和 `dw_update_time`
- 所有入仓和更新时间均不晚于本次任务实际执行时刻

## 环境要求

- Python 3.12 及以上版本
- `uv`
- Apache Doris 4.0 及以上版本
- 运行 dbmock 的主机可以访问 Doris FE 的 `9030`、`8030` 端口以及 BE 的 `8040` 端口

首次使用时创建配置文件：

```bash
cd dbmock
cp .env.example .env
uv sync
```

默认连接本机 Docker Doris：

```dotenv
DB_HOST="127.0.0.1"
DB_PORT=9030
DB_USER="root"
DB_PASSWORD=
DB_NAME="ecommerce"
```

Stream Load 的 FE HTTP 端口默认是 `8030`，需要覆盖时设置 `DB_HTTP_PORT`

## 使用流程

### 1. 准备商品目录

新环境执行完整采集：

```bash
uv run scripts/prepare_real_catalog.py
```

已有目录只执行校验：

```bash
uv run scripts/prepare_real_catalog.py --validate-only
```

采集器默认同一客户端两次请求至少间隔 0.5 秒，并支持断点续采。强制清空断点并重新采集时执行：

```bash
uv run scripts/prepare_real_catalog.py --force-download
```

完整目录会生成：

```text
data/
├── manifest.json
├── brands.json
├── categories.json
├── shops.json
├── spus.jsonl
├── skus.jsonl
├── lineage.jsonl
├── geo_regions.json
├── logistics_companies.json
├── payment_types.json
└── source/
```

`manifest.json` 保存数量、来源分布、字段血缘和文件哈希；`lineage.jsonl` 保存外部平台信息，业务维度文件不保存苏宁或当当平台属性

### 2. 初始化 Doris

```bash
make init_db
```

该命令会删除并重建 `.env` 中 `DB_NAME` 指定的数据库，然后执行 `scripts/sql/ecommerce.sql`。目标数据库中的已有数据会被永久删除

### 3. 生成数据

完整生成：

```bash
make generate
```

七天小规模链路验证：

```bash
make init_db
make smoke
```

只加载公共维度、SPU 和 SKU：

```bash
make init_db
uv run main.py --dimensions-only
```

只校验 Doris 中已有数据：

```bash
make validate
```

除 `--validate-only` 外，所有生成模式都要求 47 张目标表为空。任务中途失败后应重新执行 `make init_db`，再从头生成

## Makefile 命令

```text
make init_db      重建 Doris 业务数据库并创建表
make generate     生成完整数据
make smoke        生成七天小数据集
make validate     校验现有数据
make clean        清理虚拟环境和 Python 缓存
```

## 默认规模

| 配置         |                                    默认值 |
| ------------ | ----------------------------------------: |
| 时间范围     | 执行日期向前两个自然年至执行日期，首尾均包含 |
| 用户数       |                                     3,000 |
| SPU 数       |                                    30,000 |
| SKU 数       | 目录中对应 SPU 的真实 SKU，当前为 120,000 |
| 促销规则数   |                                        50 |
| 优惠券规则数 |                                       100 |
| 订单明细数   |                                   100,000 |
| 页面访问数   |                                    30,000 |
| 搜索数       |                                     6,000 |
| 仓库数       |                                        12 |

SKU 运营快照和库存快照按 SKU、自然日生成。12 万 SKU 的两年完整任务会产生上亿行快照，开发验证应优先使用 `make smoke`

## 生成参数

| 环境变量                       | 含义                               |
| ------------------------------ | ---------------------------------- |
| `DBMOCK_START_DATE`            | 开始日期，格式为 `YYYY-MM-DD`      |
| `DBMOCK_END_DATE`              | 结束日期，格式为 `YYYY-MM-DD`      |
| `DBMOCK_BATCH_SIZE`            | 单次 Stream Load 行数，默认 50,000 |
| `DBMOCK_SEED`                  | 随机种子，默认 42                  |
| `DBMOCK_USER_COUNT`            | 用户数                             |
| `DBMOCK_SPU_COUNT`             | 从目录中选择的 SPU 数              |
| `DBMOCK_PROMOTION_COUNT`       | 促销规则数                         |
| `DBMOCK_COUPON_COUNT`          | 优惠券规则数                       |
| `DBMOCK_ORDER_DETAIL_COUNT`    | 订单明细数，不能小于 20            |
| `DBMOCK_PAGE_VIEW_COUNT`       | 页面访问数                         |
| `DBMOCK_SEARCH_COUNT`          | 搜索数                             |
| `DBMOCK_CART_EVENTS_PER_USER`  | 每个用户的购物车事件数             |
| `DBMOCK_FAVOR_EVENTS_PER_USER` | 每个用户的收藏事件数               |
| `DBMOCK_WAREHOUSE_COUNT`       | 仓库数                             |

示例：

```bash
DBMOCK_START_DATE=2026-01-01 \
DBMOCK_END_DATE=2026-01-31 \
DBMOCK_USER_COUNT=100 \
DBMOCK_SPU_COUNT=30 \
DBMOCK_ORDER_DETAIL_COUNT=1200 \
uv run main.py
```

## 生成范围和校验

完整任务依次生成公共维度、商品、营销、交易、行为和库存快照。Doris 装载使用严格模式 JSON Stream Load，每个批次要求输入行数与成功行数一致且过滤行数为零

任务结束后会检查：

- 必填表非空以及未知维度成员完整
- SCD2 生效区间不重叠且每个业务对象只有一个当前版本
- SPU、SKU、品牌、类目和店铺引用完整
- 订单优惠、支付、运费和重量分摊一致
- 订单维度代理键命中业务发生时点版本
- 退款金额不超过实付金额
- SKU 价格事件和库存事件前后衔接
- 库存日快照与当日最后库存事件一致
- 会话汇总与页面访问、搜索明细一致
- 事实业务日期和事件时间一致
- 来源更新时间不晚于入仓时间，入仓时间不晚于任务执行时刻
- 两年历史数据的入仓时间不能全部集中在任务执行日期

## 目录结构

```text
main.py                          生成和校验入口
Makefile                         常用命令
scripts/init_db.py               Doris 建库建表入口
scripts/prepare_real_catalog.py  商品目录采集和校验入口
scripts/sql/ecommerce.sql        47 张 Doris 表的 DDL
src/catalog/                     苏宁、当当采集与目录标准化
src/database.py                  Doris Stream Load
src/entities/ecommerce.py        SQLAlchemy 表字段元数据
src/generation/batches/          各业务域生成批次
src/generation/quality.py        数据质量校验
src/settings.py                  Doris 连接和生成参数
data/                            本地目录、血缘和采集缓存，不进入 Git
```
