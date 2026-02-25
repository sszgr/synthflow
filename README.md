# SynthFlow

Async workflow orchestration framework for composing typed nodes into execution graphs.

## Status

This repository is early-stage (`0.1.0`). The core orchestration primitives are implemented:

- `Node` with typed `inputs`/`outputs`
- `Flow` execution over a shared `DataStore`
- `Parallel` branch execution and merge
- `If` conditional branch wrapper
- `NodeResult` for referencing outputs from specific upstream nodes

Some modules are present as placeholders (`execution/*`, `visualization/printer.py`), and plugin wiring is still evolving.

## Installation

From the repository root:

```bash
pip install -e .
```

## Quick Start

```python
import asyncio

from synthflow.core.flow import Flow
from synthflow.core.node import Node


class Numbers: ...
class Doubled: ...
class Total: ...


class Generate(Node):
    outputs = [Numbers]

    async def run(self):
        return {Numbers: [1, 2, 3, 4]}


class Double(Node):
    inputs = [Numbers]
    outputs = [Doubled]

    async def run(self, Numbers):
        return {Doubled: [n * 2 for n in Numbers]}


class Sum(Node):
    inputs = [Doubled]
    outputs = [Total]

    async def run(self, Doubled):
        return {Total: sum(Doubled)}


class Print(Node):
    inputs = [Total]

    async def run(self, Total):
        print(f"Result: {Total}")
        return {}


start = Generate(id="gen")
start >> Double(id="dbl") >> Sum(id="sum") >> Print(id="out")
flow = Flow(start)

asyncio.run(flow.run())
```

## Parallel Branches

Use `Parallel` to run branches concurrently. Each branch receives a copy of the current `DataStore`, then results are merged.

```python
from synthflow.core.parallel import Parallel

# start >> Parallel(branch_a, branch_b) >> join_node
```

## Referencing Specific Upstream Results

`NodeResult` lets you inject data from a specific node into runtime kwargs/args:

```python
from synthflow.core.node import NodeResult

# node.input(summary=NodeResult("sum_node_id"))
```

If `output_type` is omitted, SynthFlow resolves by producer node id.

## Conditional Branching

`If` executes a wrapped node only when a condition is true:

```python
from synthflow.core.condition import If

# start >> If(lambda store: store.has(MyType), some_node) >> next_node
```

## Plugins

The repo contains `Retry` and `Timeout` plugin classes under `synthflow/plugins/`.

- `Timeout(seconds=...)` currently wraps a coroutine with `asyncio.wait_for(...)`.
- `Retry(retries=..., delay=...)` retries a coroutine on exception.

Note: plugin decorator integration via `Node.use(...)` is not fully wired in `0.1.0`, so treat plugin APIs as in-progress.

## Example

See [`examples/general_pipeline.py`](examples/general_pipeline.py) for a larger orchestration example.
