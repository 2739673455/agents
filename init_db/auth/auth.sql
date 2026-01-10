DROP TABLE IF EXISTS `group_scope_rel`;

DROP TABLE IF EXISTS `user`;

DROP TABLE IF EXISTS `group`;

DROP TABLE IF EXISTS `scope`;

CREATE TABLE `scope` (
    `name` VARCHAR(100),
    `description` VARCHAR(100) DEFAULT NULL,
    PRIMARY KEY (`name`)
) COMMENT = '权限范围';

CREATE TABLE `group` (
    `name` VARCHAR(100) NOT NULL,
    PRIMARY KEY (`name`)
) COMMENT = '组';

CREATE TABLE `group_scope_rel` (
    `group_name` VARCHAR(100) NOT NULL,
    `scope_name` VARCHAR(100) NOT NULL,
    PRIMARY KEY (`group_name`, `scope_name`),
    FOREIGN KEY (`group_name`) REFERENCES `group` (`name`),
    FOREIGN KEY (`scope_name`) REFERENCES `scope` (`name`)
) COMMENT = '组权限关系';

CREATE TABLE `user` (
    `name` VARCHAR(100),
    `group_name` VARCHAR(100) NOT NULL,
    `hashed_password` VARCHAR(500) NOT NULL,
    `email` VARCHAR(100) NOT NULL,
    `yn` TINYINT NOT NULL DEFAULT 1,
    PRIMARY KEY (`name`),
    FOREIGN KEY (`group_name`) REFERENCES `group` (`name`)
) COMMENT = '用户';

CREATE TABLE `refresh_token` (
    `id` SERIAL PRIMARY KEY,
    `jti` VARCHAR(255) UNIQUE NOT NULL COMMENT 'JWT唯一标识',
    `username` VARCHAR(100) NOT NULL COMMENT '用户名',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `expires_at` TIMESTAMP NOT NULL COMMENT '过期时间',
    `yn` TINYINT NOT NULL DEFAULT 1,
    FOREIGN KEY (`username`) REFERENCES `user` (`name`) ON DELETE CASCADE
) COMMENT = '刷新令牌';

CREATE INDEX idx_refresh_token_jti ON refresh_token (jti);

CREATE INDEX idx_refresh_token_username ON refresh_token (username);

INSERT INTO `group` (`name`) VALUES ('root'), ('guest'), ('atguigu');

INSERT INTO
    `scope` (`name`, `description`)
VALUES ('save_metadata', '写入元数据'),
    ('clear_metadata', '清空元数据'),
    ('get_table', '获取表信息'),
    ('get_column', '获取字段信息'),
    ('retrieve_knowledge', '检索知识'),
    ('retrieve_column', '检索字段'),
    ('retrieve_cell', '检索单元格');

INSERT INTO
    group_scope_rel (`group_name`, `scope_name`)
VALUES ('root', 'save_metadata'),
    ('root', 'clear_metadata'),
    ('root', 'get_table'),
    ('root', 'get_column'),
    ('root', 'retrieve_knowledge'),
    ('root', 'retrieve_column'),
    ('root', 'retrieve_cell'),
    ('atguigu', 'get_table'),
    ('atguigu', 'get_column'),
    ('atguigu', 'retrieve_knowledge'),
    ('atguigu', 'retrieve_column'),
    ('atguigu', 'retrieve_cell');

INSERT INTO
    `user` (
        `name`,
        `group_name`,
        `hashed_password`,
        `email`,
        `yn`
    )
VALUES (
        'root',
        'root',
        '$argon2id$v=19$m=65536,t=3,p=4$fMuhnWBkGYj3r25EZnf6OA$4MRww1o4TWdfmmrYIu6H90+uQ6pMD+V6wd4B1UYnMp0',
        'root@example.com',
        1
    ),
    (
        'atguigu',
        'atguigu',
        '$argon2id$v=19$m=65536,t=3,p=4$fMuhnWBkGYj3r25EZnf6OA$4MRww1o4TWdfmmrYIu6H90+uQ6pMD+V6wd4B1UYnMp0',
        'atguigu@example.com',
        1
    ),
    (
        'zhangsan',
        'guest',
        '$argon2id$v=19$m=65536,t=3,p=4$fMuhnWBkGYj3r25EZnf6OA$4MRww1o4TWdfmmrYIu6H90+uQ6pMD+V6wd4B1UYnMp0',
        'zhangsan@example.com',
        1
    );