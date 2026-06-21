"""测试受限 Python 执行器。"""

from insight.code_exec import CodeExecutor


def test_runs_and_captures_stdout():
    r = CodeExecutor().run("print(1 + 2)")
    assert r.success
    assert r.stdout.strip() == "3"


def test_captures_error_with_traceback():
    r = CodeExecutor().run("raise ValueError('boom')")
    assert not r.success
    assert "boom" in r.error


def test_timeout_kills_runaway():
    r = CodeExecutor(timeout=1).run("while True:\n    pass")
    assert not r.success
    assert "超时" in r.error


def test_utf8_output():
    r = CodeExecutor().run("print('华东')")
    assert r.success
    assert "华东" in r.stdout
