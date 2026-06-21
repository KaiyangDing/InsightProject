"""评测层（eval）：Execution Accuracy 的结果集比对。

- evaluation.same_result：列序无关、行序无关的结果集等价判断（贴近官方 test-suite 思路）。

配合"生成 / 打分分离"的评测流水线：模型只跑一次、预测落盘，改度量只需重新打分。
"""

from insight.eval.evaluation import same_result

__all__ = ["same_result"]
