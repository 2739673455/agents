import argparse

import jieba.analyse


def is_numeric(s) -> bool:
    """判断字符串是否为数值"""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def extract_keyword(query: str):
    """从查询中提取关键词"""
    # 对查询进行分词，只提取指定词性的词
    allow_pos = (
        "n",  # 名词: 数据、服务器、表格
        "nr",  # 人名: 张三、李四
        "ns",  # 地名: 北京、上海
        "nt",  # 机构团体名: 政府、学校、某公司
        "nz",  # 其他专有名词: Unicode、哈希算法、诺贝尔奖
        "v",  # 动词: 运行、开发
        "vn",  # 名动词: 工作、研究
        "a",  # 形容词: 美丽、快速
        "an",  # 名形词: 难度、合法性、复杂度
        "eng",  # 英文
        "i",  # 成语
        "l",  # 常用固定短语
    )
    keywords = jieba.analyse.extract_tags(
        query, withWeight=False, allowPOS=allow_pos
    ) + [query]
    keywords = list(set([w for w in keywords if not is_numeric(w)]))

    return keywords


def main():
    usage = 'python extract_keyword.py "查询文本"'
    parser = argparse.ArgumentParser(description="关键词提取", usage=usage)
    parser.add_argument("query", type=str, help="查询文本")

    try:
        args = parser.parse_args()
        keywords = extract_keyword(args.query)
        print(keywords)
    except SystemExit:
        print(usage)
        raise


if __name__ == "__main__":
    main()
