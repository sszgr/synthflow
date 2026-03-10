# SynthFlow

Async workflow orchestration framework with a lightweight DSL.

> Experimental project written with Codex. Do not use in production environments.

## Why SynthFlow

- Lightweight workflow DSL for async orchestration
- Core control flow: `PARALLEL`, `IF`, `OR`, `SWITCH`
- Cross-node value passing via `ResultRef`
- Plugin pipeline for runtime policies (`Retry`, `Timeout`)
- Readable tree visualization via `flow.visualize()`

## Install

Requires Python 3.10+

### From PyPI (stable)

```bash
pip install synthflow-py
```

### From GitHub (latest development version)

```bash
pip install git+https://github.com/sszgr/synthflow.git
```

## Run Tests

Use the standard library test runner:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```


## Core Concepts

- `Node`: execution unit; implement `async def run(...)`
- `Flow`: workflow runner and visualizer
- `ResultRef`: reference another node's output in `.input(...)`
- `PARALLEL`: run branches concurrently
- `IF` / `OR` / `SWITCH`: basic control flow DSL
- `Retry` / `Timeout`: node plugins via `.use(...)`

## Quick Start

```python
import asyncio

from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef


class A(Node):
    async def run(self, a, b, c):
        return a + b + c


flow = Flow(
    A(id="a1").input(1, 2, [3, 4, 5])
    >> A(id="a2").input(
        ResultRef("a1").item(2),  # 5
        3,
        4,
    )
    >> A(id="a3").input(
        ResultRef("a2").map(lambda x: x * 2),
        1,
        1,
    )
)

flow.visualize()
asyncio.run(flow.run())
```

Get execution state and timeline:

```python
context = asyncio.run(flow.run(return_context=True))
print(context.state)      # ExecutionState.SUCCEEDED / FAILED / CANCELLED
print(context.events)     # state transitions with timestamps
print(context.node_events)  # per-node lifecycle events
print(context.store)      # DataStore
```

Stream execution events as they happen:

```python
async for event in flow.run_stream():
    if event.event == "token":
        print(event.data["text"], end="", flush=True)
```

## DSL Example (Parallel + IF + OR)

```python
from synthflow.core.dsl import IF, OR, PARALLEL
from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef

flow = Flow(
    Seed(id="seed").input([2, 5, 8, 13, 21])
    >> PARALLEL(
        SumNode(id="sum_branch").input(ResultRef("seed")),
        MaxNode(id="max_branch").input(ResultRef("seed")),
        EvenCountNode(id="even_branch").input(ResultRef("seed")),
        id="stats_parallel",
        on_conflict="overwrite",  # overwrite | keep | error
    )
    >> BuildSummary(id="summary").input(
        ResultRef("sum_branch"),
        ResultRef("max_branch"),
        ResultRef("even_branch"),
    )
    >> IF(
        condition=OR(
            lambda store: (store.get_node_result("sum_branch") or 0) > 40,
            lambda store: (store.get_node_result("max_branch") or 0) > 20,
        ),
        then_node=Alert(id="alert").input(ResultRef("summary")),
        else_node=Normal(id="normal").input(ResultRef("summary")),
        id="risk_if",
    )
)
```

### Parallel Semantics

- Branches run concurrently.
- If any branch fails, remaining branches are cancelled and the flow raises an exception.
- Merge conflict policy is controlled by `on_conflict`:
  - `overwrite` (default): later branch value overwrites earlier value
  - `keep`: preserve first value
  - `error`: raise on conflicting values

Full runnable example: [`examples/general_pipeline.py`](examples/general_pipeline.py)

## More Examples

- General pipeline: `PYTHONPATH=. python3 examples/general_pipeline.py`
- Order fulfillment (realistic e-commerce flow): `PYTHONPATH=. python3 examples/order_fulfillment_demo.py`
- API aggregation gateway flow: `PYTHONPATH=. python3 examples/api_aggregation_demo.py`
- DeepSeek streaming orchestration: `DEEPSEEK_API_KEY=... PYTHONPATH=. python3 examples/deepseek_streaming_demo.py`
- FastAPI chat SSE demo: `pip install fastapi uvicorn && DEEPSEEK_API_KEY=... PYTHONPATH=. uvicorn examples.fastapi_chat_sse_demo:app --reload`
- GitHub trending repos (recent, formatted table): `PYTHONPATH=. python3 examples/github_trending_demo.py`
- Type validation: `PYTHONPATH=. python3 examples/type_validation_demo.py`
- Graphviz export (writes `flow.dot`): `PYTHONPATH=. python3 examples/graphviz_export_demo.py`
- Execution context events: `PYTHONPATH=. python3 examples/execution_context_demo.py`

DeepSeek streaming demo environment variables:
- `DEEPSEEK_API_KEY`: required
- `DEEPSEEK_BASE_URL`: optional, defaults to `https://api.deepseek.com`
- `DEEPSEEK_MODEL`: optional, defaults to `deepseek-chat`

The FastAPI SSE demo serves a browser chat page at `http://127.0.0.1:8000/` and streams assistant tokens from `/chat/stream`.

## Plugins

Attach plugins on a node with `.use(...)`:

```python
from synthflow.plugins import Retry, Timeout

node = SomeNode().use(Retry(retries=2, delay=0.1)).use(Timeout(seconds=2.0))
```

## Visualize

`flow.visualize()` prints a tree-style orchestration view, including branch labels:

```text
Flow
└── Seed(seed)
    └── Parallel(stats_parallel)
        ├── [parallel-1] SumNode(sum_branch)
        ├── [parallel-2] MaxNode(max_branch)
        ├── [parallel-3] EvenCountNode(even_branch)
        └── BuildSummary(summary)
```

`flow.to_graphviz()` returns Graphviz DOT text for rendering diagrams in tooling/CI:

```python
dot = flow.to_graphviz()
print(dot)
```

## Type Validation

Optionally declare node input/output schemas:

```python
from synthflow.types import Field

class MyNode(Node):
    params_schema = {"x": Field(int)}
    output_schema = Field(dict)

    async def run(self, x):
        return {"value": x}
```
