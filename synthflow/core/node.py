import asyncio, inspect
from .datastore import DataStore

class NodeResult:
    def __init__(self, node_id, output_type=None, output_index=0):
        self.node_id = node_id
        self.output_type = output_type
        self.output_index = output_index

class Node:
    inputs = []
    outputs = []

    def __init__(self, id=None, **params):
        self.id = id
        self.params = params
        self.next_node = None
        self.plugins = []
        self._input_args = ()
        self._input_kwargs = {}

    def __rshift__(self, other):
        self.next_node = other
        return other

    def use(self, plugin):
        self.plugins.append(plugin)
        return self

    def input(self, *args, **kwargs):
        """传给 run() 的动态参数，可能包含 NodeResult"""
        self._input_args = args
        self._input_kwargs = kwargs
        return self

    async def execute(self, store: DataStore):
        args, kwargs = await self._collect_inputs(store)
        run_func = self._wrap_plugins(self.run)
        result = run_func(*args, **kwargs)
        if inspect.iscoroutine(result):
            result = await result

        if result:
            for dtype, value in result.items():
                store.set(dtype, value, source=self)

        if self.next_node:
            return await self.next_node.execute(store)
        return store

    async def _collect_inputs(self, store: DataStore):
        """收集 run() 参数，并解析 NodeResult"""
        # 上游依赖类型
        kwargs = {dtype.__name__: store.get(dtype) for dtype in self.inputs if store.has(dtype)}
        missing = [dtype.__name__ for dtype in self.inputs if not store.has(dtype)]
        if missing:
            raise Exception(f"{self.id or self.__class__.__name__} missing inputs: {missing}")

        # 解析 NodeResult，占位符替换为实际值
        args = self._resolve_results(self._input_args, store)
        resolved_kwargs = self._resolve_results(self._input_kwargs, store)
        kwargs.update(resolved_kwargs)

        return args, kwargs

    def _resolve_results(self, value, store: DataStore):
        """递归解析 NodeResult 占位符"""
        if isinstance(value, NodeResult):
            return self._resolve_single_result(value, store)
        elif isinstance(value, (list, tuple)):
            return type(value)(self._resolve_results(v, store) for v in value)
        elif isinstance(value, dict):
            return {k: self._resolve_results(v, store) for k, v in value.items()}
        else:
            return value

    def _resolve_single_result(self, nr: NodeResult, store: DataStore):
        # 优先根据 output_type 获取
        value = store.get(nr.output_type) if nr.output_type else None

        # 未指定类型 → 遍历 store 查找该 node_id 的输出
        if value is None:
            for dtype, val in store._data.items():
                source = store._source.get(dtype)
                if getattr(source, "id", None) == nr.node_id:
                    value = val
                    break

        if value is None:
            raise Exception(f"NodeResult from node '{nr.node_id}' not found in store")

        # 支持 output_index，如果是列表
        if isinstance(value, list) and nr.output_index not in (0, None):
            try:
                value = value[nr.output_index]
            except IndexError:
                raise Exception(f"NodeResult index {nr.output_index} out of range for node '{nr.node_id}'")

        return value

    def _wrap_plugins(self, func):
        """按注册顺序装饰插件"""
        for plugin in reversed(self.plugins):
            func = plugin(func)
        return func

    async def run(self, *args, **kwargs):
        raise NotImplementedError
