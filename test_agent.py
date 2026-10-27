import pytest
from fastapi.testclient import TestClient

from fraud_agent.api import app
from fraud_agent.graph import investigate
from fraud_agent.tools import safe_sql


def test_normal_account_closes():
    r = investigate("A100")
    assert r.decision == "close" and not r.needs_human_review


@pytest.mark.parametrize("acct,signal", [("A200", "high_velocity"), ("A300", "geo_mismatch"),
                                         ("A400", "large_transfer_after_profile_change"), ("A500", "possible_structuring")])
def test_signals_detected(acct, signal):
    assert signal in investigate(acct).signals


def test_structuring_always_escalates_to_human():
    r = investigate("A500")
    assert r.decision == "escalate" and r.needs_human_review and "human_review_queued" in r.trace
    assert "structuring" in r.policies


def test_sql_guardrail_blocks_writes():
    with pytest.raises(ValueError):
        safe_sql("DELETE FROM transactions")
    with pytest.raises(ValueError):
        safe_sql("SELECT * FROM sqlite_master")


def test_api():
    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    assert c.post("/investigate/A300").json()["decision"] in {"monitor", "escalate"}
    assert c.post("/investigate/NOPE").status_code == 404


def test_account_takeover_pattern_escalates():
    r = investigate("A400")
    assert r.decision == "escalate" and r.needs_human_review
