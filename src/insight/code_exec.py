"""Python 代码执行器：两个可互换后端，接口相同（run(code) -> ExecutionResult）。

- CodeExecutor      ：子进程 + 超时。隔离崩溃/死循环，但【不是】安全边界。
- DockerCodeExecutor：Docker 容器。断网 + 限资源 + 只读 fs + 非 root + 即弃，
                      这是【真正的安全边界】，用于跑 LLM 生成的代码。
"""

import os
import subprocess
import sys
import uuid
from dataclasses import dataclass

DOCKER_IMAGE = "insight-sandbox"


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    error: str  # 报错信息（含 traceback）；空串表示无错


class CodeExecutor:
    """子进程后端：能挡死循环/崩溃，但子进程仍可 import os / 联网 / 读 env。不是安全边界。"""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def run(self, code: str) -> ExecutionResult:
        env = {**os.environ, "PYTHONUTF8": "1"}
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, "", f"执行超时（>{self.timeout}s）")
        if proc.returncode != 0:
            return ExecutionResult(False, proc.stdout, (proc.stderr or "").strip())
        return ExecutionResult(True, proc.stdout, "")


class DockerCodeExecutor:
    """Docker 后端：断网、限内存/CPU/进程、只读根 fs、非 root、容器即弃。真正的安全边界。

    需先构建镜像：docker build -t insight-sandbox sandbox/
    """

    def __init__(self, image: str = DOCKER_IMAGE, timeout: float = 15.0):
        self.image = image
        self.timeout = timeout

    def run(self, code: str) -> ExecutionResult:
        name = f"insight-sbx-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            name,
            "--network",
            "none",  # 断网
            "--memory",
            "256m",  # 限内存
            "--cpus",
            "1",  # 限 CPU
            "--pids-limit",
            "64",  # 防 fork 炸弹
            "--read-only",  # 根 fs 只读
            "--tmpfs",
            "/tmp:rw,size=64m",  # 给一个可写的 /tmp
            "--security-opt",
            "no-new-privileges",
            "--env",
            "PYTHONUTF8=1",  # 容器内 UTF-8 输出
            "--env",
            "HOME=/tmp",  # 让需要写 home 的库落到 /tmp
            self.image,
            "python",
            "-",  # 从 stdin 读代码执行（无需转义/挂载）
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=code,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["docker", "rm", "-f", name], capture_output=True
            )  # 清残留容器
            return ExecutionResult(False, "", f"执行超时（>{self.timeout}s）")
        if proc.returncode != 0:
            return ExecutionResult(False, proc.stdout, (proc.stderr or "").strip())
        return ExecutionResult(True, proc.stdout, "")
