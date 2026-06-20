"""项目路径中心：凡是"相对项目根"的路径都从这里取，杜绝散落的相对路径。

本文件在 src/insight/ 下，parents[2] 即项目根——这样无论从哪个目录启动都不受 CWD 影响。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def resolve(path: str | Path) -> Path:
    """相对路径锚定到项目根；绝对路径原样返回。"""
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p
