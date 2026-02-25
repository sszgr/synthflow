# SynthFlow

Async workflow orchestration framework with a lightweight DSL.

> Experimental project written with Codex. Do not use in production environments.

## Install

```bash
pip install -e .
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

Full runnable example: [`examples/general_pipeline.py`](examples/general_pipeline.py)

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
