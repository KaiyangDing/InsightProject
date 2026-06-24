"""测试 API（用假编排器 override 依赖，不调真模型/库）。"""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.main import app, get_orchestrator


class FakeOrch:
    workspace = SimpleNamespace(get=lambda key: None)

    def run(self, question):
        return SimpleNamespace(
            answer="测试报告",
            steps=2,
            reviews=1,
            tool_calls=[{"name": "run_sql", "args": {"question": question}}],
        )


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_ask_endpoint():
    app.dependency_overrides[get_orchestrator] = lambda: FakeOrch()
    try:
        r = TestClient(app).post("/ask", json={"question": "q"})
        assert r.status_code == 200
        body = r.json()
        assert body["answer"] == "测试报告"
        assert body["steps"] == 2 and body["reviews"] == 1
        assert body["chart_png_base64"] is None
    finally:
        app.dependency_overrides.clear()
