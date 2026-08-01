SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS meta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE meta;

DROP TABLE IF EXISTS table_info;
CREATE TABLE table_info
(
    id VARCHAR(256) PRIMARY KEY COMMENT '表编号',
    name VARCHAR(256) COMMENT '表名称',
    role VARCHAR(256) COMMENT '表类型(fact/dim)',
    primary_key_columns JSON NOT NULL COMMENT '主键字段',
    description TEXT COMMENT '表描述'
);


DROP TABLE IF EXISTS column_info;
CREATE TABLE column_info
(
    id VARCHAR(256) PRIMARY KEY COMMENT '列编号',
    name VARCHAR(256) COMMENT '列名称',
    type VARCHAR(256) COMMENT '数据类型',
    description TEXT COMMENT '列描述',
    examples JSON COMMENT '数据示例',
    alias JSON COMMENT '列别名',
    reference_column_id VARCHAR(256) COMMENT '引用字段编号',
    index_values BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否索引字段值',
    table_id VARCHAR(256) COMMENT '所属表编号'
);

DROP TABLE IF EXISTS metric_info;
CREATE TABLE metric_info
(
    id VARCHAR(256) PRIMARY KEY COMMENT '指标编码',
    name VARCHAR(256) COMMENT '指标名称',
    description TEXT COMMENT '指标描述',
    relevant_columns JSON COMMENT '关联的列',
    alias JSON COMMENT '指标别名'
);


DROP TABLE IF EXISTS column_metric;
CREATE TABLE column_metric
(
    metric_id VARCHAR(256) COMMENT '指标编号',
    column_id VARCHAR(256) COMMENT '列编号',
    PRIMARY KEY (column_id, metric_id)
);
