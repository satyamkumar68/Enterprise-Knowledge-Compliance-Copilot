import json
import os
import httpx

from app.core.config import (
    ENABLE_QUERY_REWRITING,
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
)


REWRITER_MODEL = os.getenv("REWRITER_MODEL", "qwen3:4b")

REWRITER_TIMEOUT = httpx.Timeout(
    connect=3.0,
    read=8.0,
    write=5.0,
    pool=5.0,
)

SYSTEM_PROMPT = """You are a search query optimizer for an enterprise compliance and knowledge system.
Given an employee's question, rewrite it into a concise, focused search query to retrieve relevant policy and documentation chunks.
Rules:
- Output ONLY the search query. No markdown, no quotes, no explanations, no conversational filler.
- Preserve key terms, compliance rules, acronyms, and product names.
- If the question is already clear and concise, return it unchanged.
- Maximum 20 words.
"""

REWRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Concise search query"
        }
    },
    "required": ["query"]
}


def rewrite_query(
    question: str,
    enabled: bool | None = None,
    client: httpx.Client | None = None,
) -> str:
    """Rewrite/expand an ambiguous or conversational query for improved retrieval quality.

    Falls back immediately to the original query if query rewriting is disabled,
    times out, or encounters any error.
    """
    if not question or not question.strip():
        return ""

    clean_question = question.strip()

    is_enabled = ENABLE_QUERY_REWRITING if enabled is None else enabled
    if not is_enabled:
        return clean_question

    try:
        url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": REWRITER_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Question: {clean_question}"},
            ],
            "stream": False,
            "think": False,
            "format": REWRITE_SCHEMA,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": 0.0,
                "num_predict": 100,
            },
        }

        if client is not None:
            response = client.post(url, json=payload, timeout=REWRITER_TIMEOUT)
        else:
            response = httpx.post(url, json=payload, timeout=REWRITER_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            raw_content = (
                data.get("message", {}).get("content", "").strip()
            )
            rewritten = ""
            try:
                parsed = json.loads(raw_content)
                if isinstance(parsed, dict) and "query" in parsed and isinstance(parsed["query"], str):
                    rewritten = parsed["query"].strip()
                elif isinstance(parsed, str):
                    rewritten = parsed.strip()
            except Exception:
                rewritten = raw_content

            # Strip quotes and conversational prefixes
            rewritten = rewritten.strip('"\'`\n\r ')
            lowered = rewritten.lower()
            if (
                rewritten
                and len(rewritten) >= 3
                and not lowered.startswith("here is")
                and not lowered.startswith("search query:")
                and not lowered.startswith("we are given")
                and not lowered.startswith("steps:")
                and "\n" not in rewritten
            ):
                return rewritten
    except Exception:
        # Non-critical enhancement — retrieval must never fail because rewriter is slow or down
        pass

    return clean_question
