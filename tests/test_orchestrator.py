"""确定性测试编排器（supervisor）的工具调用循环——用假 LLM 吐 tool_calls，不调真模型。"""

from types import SimpleNamespace

from insight.agents.critic_agent import Critique
from insight.agents.orchestrator import Orchestrator, Tool
from insight.agents.report_agent import ReportAgent


# ---- 伪造"OpenAI 风格响应"的小助手 ----
def _tool_call(call_id: str, name: str, arguments: str) -> SimpleNamespace:
    """模拟一个 tool_call：tc.id / tc.function.name / tc.function.arguments(JSON 串)。"""
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _response(content=None, tool_calls=None) -> SimpleNamespace:
    """模拟 resp：resp.choices[0].message.{content, tool_calls}。"""
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeOrchestratorLLM:
    """按预设脚本依次返回响应；create 的入参一律忽略。"""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs) -> SimpleNamespace:
        return self._responses.pop(0)


def _echo_tool(calls_log: list) -> Tool:
    """测试用工具：记录被调入参、写进 workspace、回个字符串。"""

    def handler(workspace, **kwargs) -> str:
        calls_log.append(kwargs)
        workspace.put("echo", kwargs)
        return f"echo: {kwargs}"

    return Tool(
        name="echo",
        description="回显工具（测试用）",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=handler,
    )


def test_calls_tool_then_answers():
    """第1轮调 echo 工具 → 第2轮给终答。"""
    calls_log = []
    llm = FakeOrchestratorLLM(
        [
            _response(tool_calls=[_tool_call("c1", "echo", '{"text": "hi"}')]),
            _response(content="完成"),
        ]
    )
    orch = Orchestrator(llm, "fake-model", [_echo_tool(calls_log)])

    result = orch.run("随便问")

    assert result.answer == "完成"
    assert result.steps == 2
    assert result.tool_calls == [{"name": "echo", "args": {"text": "hi"}}]
    assert calls_log == [{"text": "hi"}]  # 工具真的被执行
    assert orch.workspace.get("echo") == {"text": "hi"}  # 数据进了黑板


def test_answers_without_tool():
    """模型一上来就给终答，不调工具。"""
    llm = FakeOrchestratorLLM([_response(content="直接回答")])
    orch = Orchestrator(llm, "fake-model", [_echo_tool([])])

    result = orch.run("你好")

    assert result.answer == "直接回答"
    assert result.steps == 1
    assert result.tool_calls == []


def test_budget_exhausted():
    """模型每轮都要调工具、永不收尾 → 到 max_steps 停下并返回兜底答复。"""
    llm = FakeOrchestratorLLM(
        [_response(tool_calls=[_tool_call("c1", "echo", '{"text": "x"}')])] * 2
    )
    orch = Orchestrator(llm, "fake-model", [_echo_tool([])], max_steps=2)

    result = orch.run("死循环")

    assert result.steps == 2
    assert "步数上限" in result.answer


def test_tool_error_is_fed_back_not_crash():
    """工具抛异常时编排器不崩，错误喂回后下一轮仍能给终答（验证那段 try/except 兜底）。"""

    def boom_handler(workspace, **kwargs):
        raise ValueError("炸了")

    boom = Tool(
        name="boom",
        description="必炸工具（测试用）",
        parameters={"type": "object", "properties": {}},
        handler=boom_handler,
    )
    llm = FakeOrchestratorLLM(
        [
            _response(tool_calls=[_tool_call("c1", "boom", "{}")]),
            _response(content="已处理错误"),
        ]
    )
    orch = Orchestrator(llm, "fake-model", [boom])

    result = orch.run("调用会炸的工具")  # 不抛异常即说明被兜住了

    assert result.answer == "已处理错误"
    assert result.steps == 2


class FakeCritic:
    """按预设依次返回 Critique；记录每次 review 的入参便于断言。"""

    def __init__(self, verdicts: list):
        self._verdicts = list(verdicts)
        self.seen = []

    def review(self, question, answer, evidence):
        self.seen.append((question, answer, evidence))
        return self._verdicts.pop(0)


def test_critic_approves_returns_answer():
    """候选答过 Critic 一次即通过 → 直接返回。"""
    llm = FakeOrchestratorLLM([_response(content="数码最高")])
    critic = FakeCritic([Critique(True, "通过")])
    orch = Orchestrator(llm, "fake-model", [_echo_tool([])], critic=critic)

    result = orch.run("哪个品类最高")

    assert result.answer == "数码最高"
    assert result.reviews == 1
    assert result.steps == 1
    assert critic.seen[0][1] == "数码最高"  # Critic 审到的就是候选答


def test_critic_rejects_then_revises():
    """第1次候选被打回 → 意见喂回 → 第2次候选通过。"""
    llm = FakeOrchestratorLLM([_response(content="v1"), _response(content="v2")])
    critic = FakeCritic([Critique(False, "口径不对，改"), Critique(True, "ok")])
    orch = Orchestrator(llm, "fake-model", [_echo_tool([])], critic=critic)

    result = orch.run("问题")

    assert result.answer == "v2"
    assert result.reviews == 2
    assert result.steps == 2
    assert critic.seen[0][1] == "v1" and critic.seen[1][1] == "v2"


def test_review_budget_caps_revisions():
    """Critic 一直打回 → 到 max_reviews 后直接采纳最新候选（fail-open，不死循环）。"""
    llm = FakeOrchestratorLLM(
        [_response(content="v1"), _response(content="v2"), _response(content="v3")]
    )
    critic = FakeCritic([Critique(False, "改"), Critique(False, "再改")])
    orch = Orchestrator(
        llm, "fake-model", [_echo_tool([])], critic=critic, max_reviews=2
    )

    result = orch.run("问题")

    assert result.answer == "v3"  # 第3次候选未再审，直接采纳
    assert result.reviews == 2  # 只审了 2 次（预算上限）
    assert result.steps == 3


class FakeReport:
    """假 Report：记录入参，返回预设报告文本。"""

    def __init__(self, text):
        self.text = text
        self.seen = []

    def write(self, question, evidence):
        self.seen.append((question, evidence))
        return self.text


def test_report_agent_writes(fake_llm):
    """ReportAgent.write 把模型输出原样作为报告返回。"""
    report = ReportAgent(fake_llm(["最终报告"]), "m")
    assert report.write("问题", "证据") == "最终报告"


def test_orchestrator_uses_report_agent():
    """挂了 Report → 终答用 Report 从证据写的，而非编排器自己的话。"""
    llm = FakeOrchestratorLLM([_response(content="编排器草稿")])
    report = FakeReport("结构化报告")
    orch = Orchestrator(llm, "fake-model", [_echo_tool([])], report=report)

    result = orch.run("问题")

    assert result.answer == "结构化报告"  # 用了 Report，不是 msg.content
    assert result.steps == 1


def test_critic_reviews_the_report():
    """Report + Critic 同挂：Critic 审的是报告，不是编排器草稿。"""
    llm = FakeOrchestratorLLM([_response(content="草稿")])
    report = FakeReport("报告X")
    critic = FakeCritic([Critique(True, "ok")])
    orch = Orchestrator(
        llm, "fake-model", [_echo_tool([])], critic=critic, report=report
    )

    result = orch.run("问题")

    assert result.answer == "报告X"
    assert result.reviews == 1
    assert critic.seen[0][1] == "报告X"  # critic 拿到的候选 = 报告
