"""
adam_lib.llm_client — Shared LLM client for the Writer's Nexus Suite.

Single OpenAI-compatible client that routes through the LiteLLM proxy (:4000).
Replaces the duplicate llm_client.py files in kronk/ and bka/backend/.

Usage:
    from adam_lib.llm_client import LLMClient

    client = LLMClient()                        # default model, LiteLLM proxy
    client = LLMClient(model="creative")        # gemma4:26b for writing
    client = LLMClient(model="cloud-smart")     # Claude Sonnet

    text   = client.chat(messages)              # blocking
    for chunk in client.stream(messages): ...   # streaming generator
    obj    = client.chat_json(messages)         # force JSON output + auto-parse

Environment variables:
    LLM_PROXY_URL   — base URL of the LiteLLM proxy (default http://127.0.0.1:4000/v1)
    LLM_MODEL       — default model alias (default "default" → ollama/adam:latest)
    LLM_TELEMETRY   — path to telemetry SQLite (default ~/.config/ioda/llm_telemetry.db)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from typing import Generator, Optional

import requests

log = logging.getLogger("adam_lib.llm")

LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://127.0.0.1:4000/v1")
DEFAULT_MODEL  = os.getenv("LLM_MODEL",     "default")
TELEMETRY_DB   = os.path.expanduser(
    os.getenv("LLM_TELEMETRY", "~/.config/ioda/llm_telemetry.db")
)

# Cost estimates per 1K tokens (approximate, used for telemetry only)
_COST_PER_1K: dict[str, float] = {
    "cloud-smart": 0.003,
    "cloud-fast":  0.00025,
}


class LLMClient:
    """
    Thin OpenAI-compatible client.

    All calls go through LiteLLM proxy which handles provider routing.
    Telemetry is written asynchronously to a local SQLite DB.
    """

    def __init__(
        self,
        model: str = "",
        base_url: str = "",
        api_key: str = "",
        timeout: int = 300,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ):
        self.model       = model or DEFAULT_MODEL
        self.base_url    = (base_url or LLM_PROXY_URL).rstrip("/")
        self.api_key     = api_key or os.getenv("LLM_API_KEY", "no-key")
        self.timeout     = timeout
        self.temperature = temperature
        self.max_tokens  = max_tokens
        self._telemetry_ready: bool = False

    # ── Config helpers (backwards-compat with old llm_client.py callers) ──

    def load_config(self):
        """Load model/url from ADAM-suite config.json if available."""
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
            with open(cfg_path) as f:
                cfg = json.load(f).get("ai", {})
            if cfg.get("model"):
                self.model = cfg["model"]
            if cfg.get("url"):
                self.base_url = cfg["url"].rstrip("/") + ("/v1" if ":4000" not in cfg["url"] else "/v1")
            if cfg.get("api_key"):
                self.api_key = cfg["api_key"]
            if cfg.get("timeout"):
                self.timeout = int(cfg["timeout"])
        except Exception:
            pass

    def update_config(self, provider=None, model=None, base_url=None,
                      api_key=None, **_ignored):
        if model:     self.model    = model
        if base_url:  self.base_url = base_url.rstrip("/")
        if api_key is not None: self.api_key = api_key

    # ── Core API ────────────────────────────────────────────────

    def chat(self, messages: list, stream: bool = False,
             force_json: bool = False, **kw) -> str:
        """Send a chat request. Returns full response text."""
        if stream:
            return "".join(self.stream(messages, **kw))
        return self._do_chat(messages, stream=False,
                             force_json=force_json, **kw)

    def stream(self, messages: list, **kw) -> Generator[str, None, None]:
        """Stream response tokens. Yields each token string."""
        yield from self._do_stream(messages, **kw)

    def completion(self, prompt: str, stream: bool = False,
                   force_json: bool = False, **kw) -> str:
        """Convenience wrapper: wrap raw prompt in a user message."""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, stream=stream,
                         force_json=force_json, **kw)

    def chat_json(self, messages: list, **kw) -> dict:
        """Chat with force_json=True and auto-parse the response."""
        raw = self.chat(messages, force_json=True, **kw)
        return self.extract_json(raw)

    # ── Internal HTTP ──────────────────────────────────────────

    def _build_payload(self, messages: list, stream: bool,
                       force_json: bool, **kw) -> dict:
        payload: dict = {
            "model":       kw.pop("model", self.model),
            "messages":    messages,
            "stream":      stream,
            "temperature": kw.pop("temperature", self.temperature),
        }
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        if force_json:
            payload["response_format"] = {"type": "json_object"}
        # Pass through any remaining known OpenAI params
        for k in ("max_tokens", "top_p", "stop", "seed"):
            if k in kw:
                payload[k] = kw.pop(k)
        return payload

    def _headers(self) -> dict:
        return {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _do_chat(self, messages: list, stream: bool,
                 force_json: bool, **kw) -> str:
        payload = self._build_payload(messages, stream, force_json, **kw)
        t0 = time.monotonic()
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            text = (data.get("choices", [{}])[0]
                       .get("message", {})
                       .get("content", ""))
            usage = data.get("usage", {})
            self._log_telemetry(
                model=payload["model"],
                tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
                latency_ms=int((time.monotonic() - t0) * 1000),
                ok=True,
            )
            return text
        except Exception as exc:
            log.error("LLMClient.chat failed: %s", exc)
            self._log_telemetry(model=payload.get("model", self.model),
                                tokens_in=0, tokens_out=0,
                                latency_ms=int((time.monotonic() - t0) * 1000),
                                ok=False)
            return ""

    def _do_stream(self, messages: list, **kw) -> Generator[str, None, None]:
        payload = self._build_payload(messages, stream=True,
                                      force_json=False, **kw)
        t0 = time.monotonic()
        total_tokens = 0
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                text = line.decode("utf-8") if isinstance(line, bytes) else line
                if text.startswith("data: "):
                    text = text[6:]
                if text.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(text)
                    token = (chunk.get("choices", [{}])[0]
                                 .get("delta", {})
                                 .get("content", ""))
                    if token:
                        total_tokens += 1
                        yield token
                except json.JSONDecodeError:
                    continue
        except Exception as exc:
            log.error("LLMClient.stream failed: %s", exc)
        self._log_telemetry(
            model=payload.get("model", self.model),
            tokens_in=0, tokens_out=total_tokens,
            latency_ms=int((time.monotonic() - t0) * 1000),
            ok=True,
        )

    # ── JSON helpers ───────────────────────────────────────────

    def extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks."""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        text = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return {}

    # ── Telemetry ──────────────────────────────────────────────

    def _ensure_telemetry_db(self) -> None:
        if self._telemetry_ready:
            return
        try:
            os.makedirs(os.path.dirname(TELEMETRY_DB), exist_ok=True)
            conn = sqlite3.connect(TELEMETRY_DB)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_calls (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts         TEXT    DEFAULT (datetime('now')),
                    model      TEXT,
                    tokens_in  INTEGER,
                    tokens_out INTEGER,
                    cost_usd   REAL,
                    latency_ms INTEGER,
                    ok         INTEGER
                )
            """)
            conn.commit()
            conn.close()
            self._telemetry_ready = True
        except Exception as exc:
            log.debug("Telemetry DB init failed: %s", exc)

    def _log_telemetry(self, model: str, tokens_in: int,
                       tokens_out: int, latency_ms: int, ok: bool) -> None:
        self._ensure_telemetry_db()
        if not self._telemetry_ready:
            return
        cost = (tokens_in + tokens_out) / 1000 * _COST_PER_1K.get(model, 0.0)
        try:
            conn = sqlite3.connect(TELEMETRY_DB)
            conn.execute(
                "INSERT INTO llm_calls (model, tokens_in, tokens_out, cost_usd, latency_ms, ok) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (model, tokens_in, tokens_out, cost, latency_ms, int(ok)),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            log.debug("Telemetry write failed: %s", exc)

    @staticmethod
    def query_telemetry(period_hours: int = 24) -> dict:
        """Return telemetry summary for the last N hours (for IODA queries)."""
        try:
            conn = sqlite3.connect(TELEMETRY_DB)
            rows = conn.execute("""
                SELECT model,
                       COUNT(*)           AS calls,
                       SUM(tokens_in)     AS tok_in,
                       SUM(tokens_out)    AS tok_out,
                       SUM(cost_usd)      AS cost,
                       AVG(latency_ms)    AS avg_ms
                FROM llm_calls
                WHERE ts >= datetime('now', ?)
                GROUP BY model
                ORDER BY calls DESC
            """, (f"-{period_hours} hours",)).fetchall()
            conn.close()
            return {
                "period_hours": period_hours,
                "by_model": [
                    {"model": r[0], "calls": r[1],
                     "tokens_in": r[2] or 0, "tokens_out": r[3] or 0,
                     "cost_usd": round(r[4] or 0, 6),
                     "avg_latency_ms": round(r[5] or 0, 1)}
                    for r in rows
                ],
                "total_cost_usd": round(sum((r[4] or 0) for r in rows), 6),
            }
        except Exception:
            return {"error": "telemetry DB not available"}
