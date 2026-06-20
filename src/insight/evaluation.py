"""评测工具：比对两条 SQL 的执行结果集（用于 Execution Accuracy）。

简化版 EX：按"多重集合"比对结果行——
  · 忽略行顺序（对 ORDER BY 宽松）；
  · 对列顺序敏感（保守，可能少算）。
不等于官方 test-suite EX，但作为内部基线足够，且我们会如实标注。
"""

from collections import Counter


def _row_multiset(rows: list[tuple]) -> Counter:
    def norm(v: object) -> object:
        if isinstance(v, float):
            return round(v, 6)  # 抹平 5 vs 5.0 / 浮点尾差
        return v

    return Counter(tuple(norm(v) for v in row) for row in rows)


def same_result(rows_a: list[tuple], rows_b: list[tuple]) -> bool:
    """两个结果集按多重集合是否相等（忽略行顺序）。"""
    return _row_multiset(rows_a) == _row_multiset(rows_b)
