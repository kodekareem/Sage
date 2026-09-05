"""A minimal HTTP server speaking Ollama's /api/chat protocol.

This is NOT a substitute for a real model — it exists to prove that
OllamaEngine's *network path* works end to end: real sockets, real HTTP, real
JSON encoding/decoding, and the real parser meeting text over the wire. The
replies are messy on purpose (code fences, stray prose, a malformed turn) so the
parser is exercised the way an actual small local model would exercise it.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Replies served in order. Deliberately imperfect, like a real 3B model.
REPLIES = [
    # 1: fenced JSON + trailing prose — the parser must cope.
    'Thought: I should start with the current price of NVDA.\n'
    'Action: get_quote\n'
    'Action Input: ```json\n{"ticker": "NVDA"}\n```\n'
    "I'll check this first.",
    # 2: a malformed turn — the loop must recover, not crash.
    "Hmm, let me think about what the numbers mean here.",
    # 3: a well-formed indicator call.
    'Thought: Now I need the trend and momentum picture.\n'
    'Action: calculate_technical_indicators\n'
    'Action Input: {"ticker": "NVDA"}',
    # 4: final answer as JSON with prose after it.
    'Thought: I have enough to judge.\n'
    'Final Answer: {"recommendation": "BUY", "confidence": "medium", '
    '"rationale": "Price sits above the 200-day average with a golden cross, '
    'and momentum is not yet overbought."}\n'
    "That is my conclusion.",
]


class Handler(BaseHTTPRequestHandler):
    index = 0

    def do_GET(self):  # /api/tags — availability probe
        if self.path.startswith("/api/tags"):
            body = json.dumps({"models": [{"name": "mock-model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):  # /api/chat — the completion endpoint
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        # Echo back that we received a real message list (sanity for the test).
        assert isinstance(payload.get("messages"), list), "no messages in request"

        reply = REPLIES[min(Handler.index, len(REPLIES) - 1)]
        Handler.index += 1

        body = json.dumps({"message": {"role": "assistant", "content": reply}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the test output clean
        pass


def serve(port: int = 11599) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
