"""测试代码执行器（子进程后端 + Docker 后端）。"""

import shutil
import subprocess

import pytest

from insight.tools.code_exec import DockerCodeExecutor, CodeExecutor


def _sandbox_ready() -> bool:
    """Docker 可用且 insight-sandbox 镜像已构建。"""
    if shutil.which("docker") is None:
        return False
    r = subprocess.run(
        ["docker", "image", "inspect", "insight-sandbox"], capture_output=True
    )
    return r.returncode == 0


requires_sandbox = pytest.mark.skipif(
    not _sandbox_ready(), reason="需要 Docker 且已 build insight-sandbox 镜像"
)


# ---- 子进程后端 ----
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


# ---- Docker 后端（无 Docker/镜像则跳过）----
@requires_sandbox
def test_docker_runs_pandas():
    r = DockerCodeExecutor().run(
        "import pandas as pd; print(pd.DataFrame({'a': [1, 2]})['a'].sum())"
    )
    assert r.success
    assert "3" in r.stdout


@requires_sandbox
def test_docker_network_is_blocked():
    code = (
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('http://example.com', timeout=3)\n"
        "    print('NETWORK_OK')\n"
        "except Exception:\n"
        "    print('NETWORK_BLOCKED')\n"
    )
    r = DockerCodeExecutor().run(code)
    assert r.success
    assert "NETWORK_BLOCKED" in r.stdout
