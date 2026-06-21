"""受限 Python 代码执行器。

⚠️ 安全说明：当前后端 = 【子进程 + 超时】。
  - 能做到：隔离崩溃/死循环、不污染主进程、强制超时、捕获输出与报错。
  - 做不到：对抗恶意代码（子进程仍可 import os / 读文件 / 联网 / 读 env）。
故意【不】用"危险词黑名单"（security theater）。真正的安全边界见后续 Docker 后端。
仅用于跑较可信的 LLM 生成分析代码（dev/demo）。
"""

import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    error: str  # 报错信息（含 traceback）；空串表示无错


class CodeExecutor:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def run(self, code: str) -> ExecutionResult:
        # 强制子进程用 UTF-8 输出（否则中文/emoji 在 Windows GBK 下会崩）
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
            # 把 traceback 放进 error——以后可像 SQL 那样喂回模型让它改代码
            return ExecutionResult(False, proc.stdout, (proc.stderr or "").strip())
        return ExecutionResult(True, proc.stdout, "")
