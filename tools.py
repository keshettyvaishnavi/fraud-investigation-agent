"""Tools the agent is allowed to call. Each tool is small, read only, and validated."""
import re
import sqlite3
from pathlib import Path
from statistics import mean

from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from data import DB_PATH, build_database

POLICY_DIR = Path(__file__).resolve().parent
POLICY_FILES = ["high_velocity", "geo_mismatch", "large_transfer", "structuring"]
ALLOWED_TABLES = {"accounts", "transactions"}
BLOCKED = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace)\b", re.I)


class SqlResult(BaseModel):
    columns: list[str]
    rows: list[list]


class RiskScore(BaseModel):
    account_id: str
    score: float = Field(ge=0, le=1)
    signals: list[str]


class PolicyHit(BaseModel):
    policy: str
    text: str
    similarity: float


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        build_database()
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return con


def safe_sql(query: str, params: tuple = (), limit: int = 200) -> SqlResult:
    """Run a read only SELECT against approved tables. Guardrail for controlled SQL retrieval."""
    q = query.strip().rstrip(";")
    if not q.lower().startswith("select") or BLOCKED.search(q) or ";" in q:
        raise ValueError("Only single read only SELECT statements are allowed")
    tables = set(re.findall(r"\b(?:from|join)\s+([a-zA-Z_]+)", q, re.I))
    if not tables or not tables.issubset(ALLOWED_TABLES):
        raise ValueError(f"Query touches tables outside the allow list: {tables - ALLOWED_TABLES}")
    with _connect() as con:
        cur = con.execute(f"{q} LIMIT {int(limit)}", params)
        cols = [c[0] for c in cur.description]
        return SqlResult(columns=cols, rows=[list(r) for r in cur.fetchall()])


def account_profile(account_id: str) -> dict:
    res = safe_sql("SELECT account_id, customer_name, home_country, travel_notice, last_profile_change FROM accounts WHERE account_id = ?", (account_id,))
    if not res.rows:
        raise KeyError(f"Unknown account {account_id}")
    return dict(zip(res.columns, res.rows[0]))


def recent_transactions(account_id: str, hours: int = 24) -> list[dict]:
    res = safe_sql(
        "SELECT ts, amount, country, channel, payee, is_new_payee FROM transactions "
        "WHERE account_id = ? AND ts >= datetime('2026-10-20T12:00:00', ?) ORDER BY ts DESC",
        (account_id, f"-{hours} hours"),
    )
    return [dict(zip(res.columns, r)) for r in res.rows]


def risk_score(account_id: str) -> RiskScore:
    """Simple explainable scoring model standing in for a production ML model."""
    recent = recent_transactions(account_id, 24)
    history = safe_sql(
        "SELECT date(ts) AS d, count(*) AS n FROM transactions WHERE account_id = ? GROUP BY date(ts)",
        (account_id,),
    )
    daily_avg = mean([r[1] for r in history.rows]) if history.rows else 1
    profile = account_profile(account_id)
    signals, score = [], 0.05

    last_hour = [t for t in recent if t["ts"] >= "2026-10-20T11:00:00" and t["channel"] == "card"]
    if len(last_hour) > 8 or len(recent) > 4 * daily_avg:
        signals.append("high_velocity"); score += 0.35
    countries = {t["country"] for t in recent[:10]}
    if len(countries) > 1 and not profile["travel_notice"]:
        signals.append("geo_mismatch"); score += 0.4
    big_new = [t for t in recent if t["amount"] > 10000 and t["is_new_payee"]]
    if big_new and profile["last_profile_change"] >= "2026-10-13":
        signals.append("large_transfer_after_profile_change"); score += 0.45
    near_10k = [t for t in recent if t["channel"] == "cash_deposit" and 9000 <= t["amount"] < 10000]
    if len(near_10k) >= 3:
        signals.append("possible_structuring"); score += 0.5
    return RiskScore(account_id=account_id, score=min(round(score, 2), 1.0), signals=signals)


class PolicyIndex:
    """Small retrieval index over policy documents. Swap TF IDF for embeddings plus FAISS in production."""

    def __init__(self, folder: Path = POLICY_DIR):
        self.docs = {name: (folder / f"{name}.md").read_text() for name in POLICY_FILES}
        self.names = list(self.docs)
        self.vec = TfidfVectorizer(stop_words="english")
        self.matrix = self.vec.fit_transform(self.docs.values())

    def search(self, query: str, k: int = 2) -> list[PolicyHit]:
        sims = cosine_similarity(self.vec.transform([query]), self.matrix)[0]
        order = sims.argsort()[::-1][:k]
        return [PolicyHit(policy=self.names[i], text=self.docs[self.names[i]], similarity=round(float(sims[i]), 3)) for i in order if sims[i] > 0]
