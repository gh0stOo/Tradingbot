from backend.app.services.orchestrator import Orchestrator


def test_orchestrator_schema_valid():
    orch = Orchestrator()
    completion = orch.llm.complete("test")
    assert {"title", "script", "cta"}.issubset(completion.keys())
