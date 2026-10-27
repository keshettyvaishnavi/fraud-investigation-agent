"""LLM wrapper. Uses OpenAI when OPENAI_API_KEY is set, otherwise a deterministic offline writer so the project runs anywhere."""
import json
import os


def write_summary(case: dict) -> str:
    if os.getenv("OPENAI_API_KEY"):
        from openai import OpenAI
        client = OpenAI()
        prompt = (
            "You are helping a bank fraud analyst. Write a short, factual case summary using only the evidence given. "
            "Cite policy ids in brackets. Do not invent facts.\n\n" + json.dumps(case, default=str, indent=2)
        )
        resp = client.chat.completions.create(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), messages=[{"role": "user", "content": prompt}], temperature=0)
        return resp.choices[0].message.content.strip()
    signals = ", ".join(case["risk"]["signals"]) or "no strong signals"
    policies = ", ".join(f"[{p['policy']}]" for p in case["policies"]) or "none"
    return (
        f"Account {case['account_id']} scored {case['risk']['score']} with signals: {signals}. "
        f"Reviewed {len(case['transactions'])} transactions from the last 24 hours. "
        f"Relevant policies: {policies}. Recommended action: {case['decision']}."
    )
