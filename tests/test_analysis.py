"""测试 pandas 分析的数据注入机制（用子进程执行器，确定性）。"""

from insight.analysis import build_analysis_code
from insight.code_exec import CodeExecutor


def test_data_injected_and_computed():
    full = build_analysis_code(
        ["region", "total"],
        [("华东", 100), ("华北", 50)],
        "print(int(df['total'].sum()))",
    )
    r = CodeExecutor().run(full)
    assert r.success, r.error
    assert "150" in r.stdout


def test_chinese_data_round_trips():
    full = build_analysis_code(
        ["region"], [("华东",), ("华北",)], "print('华东' in df['region'].tolist())"
    )
    r = CodeExecutor().run(full)
    assert r.success, r.error
    assert "True" in r.stdout
