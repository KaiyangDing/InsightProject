"""评测工具：比对两条 SQL 的执行结果集（用于 Execution Accuracy）。

列顺序无关的简化 EX：
  · 忽略行顺序（对 ORDER BY 宽松——这是仍保留的简化）；
  · 忽略列顺序，但保持行内关联（尝试列的排列匹配，贴近官方 test-suite 做法）。
不等于官方 test-suite EX，但作为内部基线足够，且我们如实标注。
"""

from collections import Counter
from itertools import permutations

_MAX_COLS_FOR_PERMUTE = 6  # 列数超过此值放弃全排列（c! 会爆），退化为严格比对


def _normalize(v: object) -> object:
    if isinstance(v, float):
        return round(v, 6)  # 抹平 5 vs 5.0 / 浮点尾差
    return v


def _multiset(rows: list[tuple]) -> Counter:
    return Counter(tuple(_normalize(v) for v in row) for row in rows)


def same_result(our_rows: list[tuple], gold_rows: list[tuple]) -> bool:
    """两个结果集是否等价：忽略行序、忽略列序，但保持行内关联。"""
    if len(our_rows) != len(gold_rows):
        return False
    if not our_rows:  # 两边都空
        return True
    n_cols = len(our_rows[0])
    if n_cols != len(gold_rows[0]):
        return False

    gold_ms = _multiset(gold_rows)
    our_norm = [tuple(_normalize(v) for v in row) for row in our_rows]  # 预归一化一次

    # 列数太多就不做全排列，退回严格（同序）比对，避免 c! 爆炸
    if n_cols > _MAX_COLS_FOR_PERMUTE:
        return Counter(our_norm) == gold_ms

    # 尝试我们列的每一种排列，有一种能让结果集相等即算对
    for perm in permutations(range(n_cols)):
        permuted_ms = Counter(tuple(row[i] for i in perm) for row in our_norm)
        if permuted_ms == gold_ms:
            return True
    return False
