"""测试 EX 结果集比对（evaluation.same_result）。"""

from insight.eval.evaluation import same_result


def test_identical_matches():
    assert same_result([(1, "a"), (2, "b")], [(1, "a"), (2, "b")])


def test_row_order_ignored():
    assert same_result([(2, "b"), (1, "a")], [(1, "a"), (2, "b")])


def test_column_order_ignored():
    # (city, count) vs (count, city)：列顺序颠倒但数据一致 → 应相等
    assert same_result([("NY", 3), ("LA", 2)], [(3, "NY"), (2, "LA")])


def test_wrong_association_not_matched():
    # 列序无关，但行内关联必须保持：count 和 city 对错了 → 不相等
    assert not same_result([("NY", 2), ("LA", 3)], [(3, "NY"), (2, "LA")])


def test_different_values_not_matched():
    assert not same_result([(1, "a")], [(2, "a")])


def test_different_row_count_not_matched():
    assert not same_result([(1, "a")], [(1, "a"), (2, "b")])


def test_float_int_normalized():
    assert same_result([(5.0,)], [(5,)])  # 5 vs 5.0 不应判为不等
