"""LangGraph workflow: gather evidence, score, retrieve policy, decide, apply guardrails, then close or escalate to a human."""
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from llm import write_summary
from tools import PolicyIndex, account_profile, recent_transactions, risk_score

POLICIES = PolicyIndex()
SIGNAL_QUERIES = {
    "high_velocity": "many transactions short time velocity",
    "geo_mismatch": "two countries travel notice geographic",
    "large_transfer_after_profile_change": "large outbound transfer new payee password reset",
    "possible_structuring": "cash deposits below 10000 structuring compliance",
}


class CaseReport(BaseModel):
    account_id: str
    risk_score: float
    signals: list[str]
    policies: list[str]
    decision: Literal["close", "monitor", "escalate"]
    needs_human_review: bool
    summary: str
    trace: list[str]


class State(TypedDict, total=False):
    account_id: str
    profile: dict
    transactions: list
    risk: dict
    policies: list
    decision: str
    needs_human_review: bool
    summary: str
    trace: list


def _log(state: State, step: str) -> list:
    return state.get("trace", []) + [step]


def gather_evidence(state: State) -> State:
    acct = state["account_id"]
    return {"profile": account_profile(acct), "transactions": recent_transactions(acct, 24), "trace": _log(state, "gather_evidence")}


def score(state: State) -> State:
    return {"risk": risk_score(state["account_id"]).model_dump(), "trace": _log(state, "score")}


def retrieve_policy(state: State) -> State:
    hits = {}
    for sig in state["risk"]["signals"]:
        for h in POLICIES.search(SIGNAL_QUERIES[sig], k=1):
            hits[h.policy] = h.model_dump()
    return {"policies": list(hits.values()), "trace": _log(state, "retrieve_policy")}


def decide(state: State) -> State:
    s = state["risk"]["score"]
    decision = "escalate" if s >= 0.6 else "monitor" if s >= 0.3 else "close"
    return {"decision": decision, "trace": _log(state, "decide")}


def guardrails(state: State) -> State:
    """Business rules the agent can never override, no matter what the model says."""
    signals = set(state["risk"]["signals"])
    decision = state["decision"]
    if signals & {"possible_structuring", "large_transfer_after_profile_change"}:
        decision = "escalate"
    needs_human = decision == "escalate" or bool(signals and decision == "close")
    return {"decision": decision, "needs_human_review": needs_human, "trace": _log(state, "guardrails")}


def route(state: State) -> str:
    return "human_review" if state["needs_human_review"] else "summarize"


def human_review(state: State) -> State:
    return {"trace": _log(state, "human_review_queued")}


def summarize(state: State) -> State:
    case = {k: state[k] for k in ["account_id", "risk", "policies", "transactions", "decision"]}
    return {"summary": write_summary(case), "trace": _log(state, "summarize")}


def build_graph():
    g = StateGraph(State)
    for name, fn in [("gather_evidence", gather_evidence), ("score", score), ("retrieve_policy", retrieve_policy),
                     ("decide", decide), ("guardrails", guardrails), ("human_review", human_review), ("summarize", summarize)]:
        g.add_node(name, fn)
    g.add_edge(START, "gather_evidence")
    g.add_edge("gather_evidence", "score")
    g.add_edge("score", "retrieve_policy")
    g.add_edge("retrieve_policy", "decide")
    g.add_edge("decide", "guardrails")
    g.add_conditional_edges("guardrails", route, {"human_review": "human_review", "summarize": "summarize"})
    g.add_edge("human_review", "summarize")
    g.add_edge("summarize", END)
    return g.compile()


GRAPH = build_graph()


def investigate(account_id: str) -> CaseReport:
    out = GRAPH.invoke({"account_id": account_id, "trace": []})
    return CaseReport(
        account_id=account_id,
        risk_score=out["risk"]["score"],
        signals=out["risk"]["signals"],
        policies=[p["policy"] for p in out["policies"]],
        decision=out["decision"],
        needs_human_review=out["needs_human_review"],
        summary=out["summary"],
        trace=out["trace"],
    )


if __name__ == "__main__":
    import sys
    for acct in sys.argv[1:] or ["A100", "A200", "A300", "A400", "A500"]:
        print(investigate(acct).model_dump_json(indent=2))
