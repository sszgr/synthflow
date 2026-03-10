import asyncio
import json
import os
from typing import Any
from urllib import error, request

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
    async def run(self, topic):
        return {
            "system": "You are a concise technical architect.",
            "user": (
                "Design a compact event-driven workflow for the topic below. "
                "Return numbered steps and key failure handling.\n\n"
                f"Topic: {topic}"
            ),
        }


class StreamDeepSeek(Node):
    async def run(self, config: dict[str, str], prompt: dict[str, str]):
        return await asyncio.to_thread(self._stream_completion, config, prompt)

    def _stream_completion(self, config: dict[str, str], prompt: dict[str, str]) -> str:
        payload = {
            "model": config["model"],
            "stream": True,
            "messages": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{config['base_url'].rstrip('/')}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )

        chunks: list[str] = []
        print("deepseek_stream:", flush=True)
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

    def _extract_delta(self, data: str) -> str:
        event = json.loads(data)
        choices = event.get("choices") or []
        if not choices:
            return ""

        delta: dict[str, Any] = choices[0].get("delta") or {}
        reasoning = delta.get("reasoning_content")
        content = delta.get("content")

        if reasoning:
            return reasoning
        if content:
            return content
        return ""


class PrintSummary(Node):
    async def run(self, answer):
        print("\nfinal_answer_length:", len(answer))
        return answer


async def main():
    flow = Flow(
        LoadConfig(id="config")
        >> BuildPrompt(id="prompt").input(topic="build a customer support triage workflow")
        >> StreamDeepSeek(id="deepseek_stream").input(
            config=ResultRef("config"),
            prompt=ResultRef("prompt"),
        )
        >> PrintSummary(id="summary").input(answer=ResultRef("deepseek_stream"))
    )

    flow.visualize()

    async for event in flow.run_stream():
        if event.event == "token":
            print(event.data["text"], end="", flush=True)
        elif event.event == "flow_state" and event.data["state"] == "failed":
            print(f"\nflow_failed: {event.data['message']}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
