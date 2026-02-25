# examples/news_pipeline.py
import asyncio
from synthflow.core.node import Node, NodeResult
from synthflow.core.parallel import Parallel
from synthflow.core.flow import Flow
from synthflow.plugins.retry import Retry
from synthflow.plugins.timeout import Timeout

# 数据类型
class InputData: pass
class ProcessedData: pass
class FinalResult: pass

# -------------------------
# 节点定义
# -------------------------
class Generator(Node):
    outputs = [InputData]
    async def run(self):
        await asyncio.sleep(0.1)
        return {InputData: [1,2,3,4,5]}

class Processor(Node):
    inputs = [InputData]
    outputs = [ProcessedData]
    async def run(self, InputData):
        await asyncio.sleep(0.1)
        return {ProcessedData: [x*2 for x in InputData]}

class Summarizer(Node):
    inputs = [ProcessedData]
    outputs = [FinalResult]
    def __init__(self, id=None, method="sum"):
        super().__init__(id=id, method=method)
    async def run(self, ProcessedData, method):
        await asyncio.sleep(0.1)
        if method == "sum":
            return {FinalResult: sum(ProcessedData)}
        elif method == "max":
            return {FinalResult: max(ProcessedData)}
        else:
            return {FinalResult: ProcessedData}

class Output(Node):
    inputs = [FinalResult]
    async def run(self, FinalResult):
        print(f"Output: {FinalResult}")
        return {}

# -------------------------
# 流程编排
# -------------------------
flow = Flow(
    Generator(id="gen").use(Retry(2))
    >> Parallel(
        Processor(id="proc1") >> Summarizer(id="sum1", method="sum"),
        Processor(id="proc2") >> Summarizer(id="sum2", method="max")
    )
    >> Output(id="out").input(NodeResult("sum1"), method="sum")  # 参数覆盖
)

# -------------------------
# 可视化
# -------------------------
flow.visualize()

# -------------------------
# 执行
# -------------------------
asyncio.run(flow.run())