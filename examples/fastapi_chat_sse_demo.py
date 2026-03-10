import json
import os
from urllib import error, request

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef


class LoadConfig(Node):
    async def run(self):
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required")

        return {
            "api_key": api_key,
            "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        }


class BuildPrompt(Node):
    async def run(self, message):
        return {
            "system": "You are a concise assistant for a browser chat UI.",
            "user": message,
        }


class StreamDeepSeek(Node):
    async def run(self, config, prompt):
        import asyncio

        return await asyncio.to_thread(self._stream_completion, config, prompt)

    def _stream_completion(self, config, prompt):
        payload = {
            "model": config["model"],
            "stream": True,
            "messages": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
        }
        req = request.Request(
            url=f"{config['base_url'].rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )

        chunks = []
        try:
            with request.urlopen(req, timeout=300) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    piece = self._extract_delta(data)
                    if not piece:
                        continue
                    self.emit_event("token", {"text": piece})
                    chunks.append(piece)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {detail}") from exc

        return "".join(chunks).strip()

    def _extract_delta(self, data):
        event = json.loads(data)
        choices = event.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        return delta.get("reasoning_content") or delta.get("content") or ""


def build_chat_flow(message: str) -> Flow:
    return Flow(
        LoadConfig(id="config")
        >> BuildPrompt(id="prompt").input(message=message)
        >> StreamDeepSeek(id="assistant").input(
            config=ResultRef("config"),
            prompt=ResultRef("prompt"),
        )
    )


app = FastAPI(title="SynthFlow Chat SSE Demo")


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SynthFlow Chat SSE Demo</title>
  <style>
    :root {
      --bg: #f4efe6;
      --panel: #fffaf1;
      --ink: #1d2433;
      --accent: #b45309;
      --line: #d9c8a9;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, #fff8e8 0, transparent 30%),
        linear-gradient(180deg, #f7f1e7 0%, var(--bg) 100%);
      color: var(--ink);
    }
    .wrap {
      max-width: 860px;
      margin: 40px auto;
      padding: 24px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 10px 30px rgba(65, 46, 12, 0.08);
    }
    h1 {
      margin: 0 0 16px;
      font-size: 32px;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
    }
    textarea {
      width: 100%;
      min-height: 110px;
      padding: 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: #fffdf8;
      font: inherit;
      resize: vertical;
    }
    button {
      border: 0;
      border-radius: 14px;
      padding: 0 18px;
      background: var(--accent);
      color: white;
      font: inherit;
      cursor: pointer;
    }
    pre {
      margin: 18px 0 0;
      min-height: 220px;
      padding: 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: #fffdf8;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .meta {
      margin-top: 12px;
      color: #6b7280;
      font-size: 14px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h1>SynthFlow Chat SSE</h1>
      <div class="row">
        <textarea id="message">Design a customer support triage workflow with retries, timeouts, and human fallback.</textarea>
        <button id="send">Send</button>
      </div>
      <div class="meta" id="meta">Idle</div>
      <pre id="output"></pre>
    </div>
  </div>
  <script>
    const send = document.getElementById("send");
    const output = document.getElementById("output");
    const meta = document.getElementById("meta");
    const message = document.getElementById("message");
    let source = null;

    send.onclick = () => {
      if (source) {
        source.close();
      }
      output.textContent = "";
      meta.textContent = "Streaming...";
      const q = encodeURIComponent(message.value);
      source = new EventSource(`/chat/stream?message=${q}`);

      source.addEventListener("token", (event) => {
        const data = JSON.parse(event.data);
        output.textContent += data.text;
      });

      source.addEventListener("done", (event) => {
        const data = JSON.parse(event.data);
        meta.textContent = `Done | ${data.model}`;
        source.close();
      });

      source.addEventListener("failure", (event) => {
        meta.textContent = "Failed";
        const data = JSON.parse(event.data);
        output.textContent += `\\n\\n[error] ${data.message}`;
        source.close();
      });

      source.onerror = () => {
        meta.textContent = "Connection closed";
      };
    };
  </script>
</body>
</html>
"""


@app.get("/chat/stream")
async def chat_stream(message: str = Query(..., min_length=1)):
    async def event_stream():
        flow = build_chat_flow(message)
        try:
            async for event in flow.run_stream():
                if event.event == "token":
                    yield _sse("token", event.data)
                elif event.event == "flow_state" and event.data["state"] == "failed":
                    yield _sse("failure", {"message": event.data["message"]})
        except Exception as exc:
            yield _sse("failure", {"message": str(exc)})
            return

        result = flow.last_execution.store.get_node_result("assistant")
        model = flow.last_execution.store.get_node_result("config")["model"]
        yield _sse("done", {"message": result, "model": model})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
