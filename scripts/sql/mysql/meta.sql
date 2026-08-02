SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS meta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE meta;

DROP TABLE IF EXISTS column_metric;
DROP TABLE IF EXISTS metric_info;
DROP TABLE IF EXISTS column_info;
DROP TABLE IF EXISTS table_info;

CREATE TABLE table_info
(
    name VARCHAR(256) PRIMARY KEY COMMENT '表名称',
    role VARCHAR(256) COMMENT '表类型(fact/dim)',
    description TEXT COMMENT '表描述',
    primary_key_columns JSON NOT NULL COMMENT '主键字段',
    meta_version INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '元数据版本',
    index_version INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '向量索引版本'
);


CREATE TABLE column_info
(
    t_name VARCHAR(256) COMMENT '所属表名称',
    name VARCHAR(256) COMMENT '字段名称',
    type VARCHAR(256) COMMENT '数据类型',
    description TEXT COMMENT '列描述',
    alias JSON COMMENT '列别名',
    examples JSON COMMENT '数据示例',
    reference_t_name VARCHAR(256) COMMENT '引用表名称',
    reference_c_name VARCHAR(256) COMMENT '引用字段名称',
    index_values BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否索引字段值',
    meta_version INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '元数据版本',
    index_version INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '向量索引版本',
    PRIMARY KEY (t_name, name),
    FOREIGN KEY (t_name) REFERENCES table_info (name) ON DELETE CASCADE,
    FOREIGN KEY (reference_t_name, reference_c_name)
    REFERENCES column_info (t_name, name) ON DELETE SET NULL
);

CREATE TABLE metric_info
(
    name VARCHAR(256) PRIMARY KEY COMMENT '指标名称',
    description TEXT COMMENT '指标描述',
    alias JSON COMMENT '指标别名',
    meta_version INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '元数据版本',
    index_version INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '向量索引版本'
);


CREATE TABLE column_metric
(
    t_name VARCHAR(256) COMMENT '表名称',
    c_name VARCHAR(256) COMMENT '字段名称',
    metric_name VARCHAR(256) COMMENT '指标名称',
    PRIMARY KEY (t_name, c_name, metric_name),
    FOREIGN KEY (t_name, c_name)
    REFERENCES column_info (t_name, name) ON DELETE CASCADE,
    FOREIGN KEY (metric_name) REFERENCES metric_info (name) ON DELETE CASCADE
);
