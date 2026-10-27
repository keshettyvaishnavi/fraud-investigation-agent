"""Creates a small SQLite database of synthetic accounts and transactions for local demos and tests."""
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "bank.db"


def build_database(path: Path = DB_PATH, seed: int = 7) -> Path:
    random.seed(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.executescript(
        """
        CREATE TABLE accounts (
            account_id TEXT PRIMARY KEY,
            customer_name TEXT,
            home_country TEXT,
            travel_notice INTEGER,
            last_profile_change TEXT
        );
        CREATE TABLE transactions (
            txn_id INTEGER PRIMARY KEY,
            account_id TEXT,
            ts TEXT,
            amount REAL,
            country TEXT,
            channel TEXT,
            payee TEXT,
            is_new_payee INTEGER
        );
        """
    )
    now = datetime(2026, 10, 20, 12, 0, 0)
    accounts = [
        ("A100", "Normal Customer", "US", 0, (now - timedelta(days=200)).isoformat()),
        ("A200", "Velocity Case", "US", 0, (now - timedelta(days=90)).isoformat()),
        ("A300", "Geo Mismatch Case", "US", 0, (now - timedelta(days=60)).isoformat()),
        ("A400", "Account Takeover Case", "US", 0, (now - timedelta(days=2)).isoformat()),
        ("A500", "Structuring Case", "US", 0, (now - timedelta(days=300)).isoformat()),
    ]
    cur.executemany("INSERT INTO accounts VALUES (?,?,?,?,?)", accounts)

    rows = []
    def add(acct, ts, amt, country="US", channel="card", payee="merchant", new=0):
        rows.append((acct, ts.isoformat(), round(amt, 2), country, channel, payee, new))

    for acct in ["A100", "A200", "A300", "A400", "A500"]:
        for d in range(30):
            for _ in range(random.randint(1, 3)):
                add(acct, now - timedelta(days=d, hours=random.randint(1, 20)), random.uniform(5, 120))

    for m in range(12):
        add("A200", now - timedelta(minutes=5 * m), random.uniform(20, 300))

    add("A300", now - timedelta(minutes=30), 85.0, country="US")
    add("A300", now - timedelta(minutes=10), 640.0, country="RO")

    add("A400", now - timedelta(hours=3), 14500.0, channel="wire", payee="New Payee LLC", new=1)

    for h in range(4):
        add("A500", now - timedelta(hours=6 * h), 9500.0 + h * 100, channel="cash_deposit", payee="branch")

    cur.executemany(
        "INSERT INTO transactions (account_id, ts, amount, country, channel, payee, is_new_payee) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    con.close()
    return path


if __name__ == "__main__":
    print(f"Database created at {build_database()}")
