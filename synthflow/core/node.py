import inspect
from .datastore import DataStore


class ResultRef:
    def __init__(self, node_id, output_type=None, output_index=None, transform=None):
        self.node_id = node_id
        self.output_type = output_type
        self.output_index = output_index
        self.transform = transform

    def map(self, transform):
        if self.transform is None:
            chained = transform
        else:
            def chained(value):
                return transform(self.transform(value))
        return ResultRef(
            node_id=self.node_id,
            output_type=self.output_type,
            output_index=self.output_index,
            transform=chained,
        )

    def item(self, index):
        return self.map(lambda value: value[index])


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
        tail = self
        while tail.next_node is not None:
            tail = tail.next_node
        tail.next_node = other
        return self

    def use(self, plugin):
        self.plugins.append(plugin)
        return self

    def input(self, *args, **kwargs):
        """Dynamic args/kwargs for run(); values can include ResultRef placeholders."""
        self._input_args = args
        self._input_kwargs = kwargs
        return self

    async def execute(self, store: DataStore):
        args, kwargs = await self._collect_inputs(store)
        result = await self._invoke_with_plugins(store, args, kwargs)
        store.set_node_result(self.id, result)
        self._persist_result(store, result)

        if self.next_node:
            return await self.next_node.execute(store)
        return store

    async def _collect_inputs(self, store: DataStore):
        """Collect run() args and resolve ResultRef placeholders."""
        kwargs = {dtype.__name__: store.get(dtype) for dtype in self.inputs if store.has(dtype)}
        missing = [dtype.__name__ for dtype in self.inputs if not store.has(dtype)]
        if missing:
            raise Exception(f"{self.id or self.__class__.__name__} missing inputs: {missing}")

        args = self._resolve_results(self._input_args, store)
        kwargs.update(self.params)
        resolved_kwargs = self._resolve_results(self._input_kwargs, store)
        kwargs.update(resolved_kwargs)

        return args, kwargs

    def _resolve_results(self, value, store: DataStore):
        """Recursively resolve ResultRef placeholders."""
        if isinstance(value, ResultRef):
            return self._resolve_single_result(value, store)
        if isinstance(value, (list, tuple)):
            return type(value)(self._resolve_results(v, store) for v in value)
        if isinstance(value, dict):
            return {k: self._resolve_results(v, store) for k, v in value.items()}
        return value

    def _resolve_single_result(self, nr: ResultRef, store: DataStore):
        value = store.get_node_result(nr.node_id)
        if value is None:
            value = store.get_from_node(nr.node_id, nr.output_type)
        if value is None:
            value = store.get(nr.output_type) if nr.output_type else None

        if value is None:
            for dtype, val in store._data.items():
                source = store._source.get(dtype)
                if getattr(source, "id", None) == nr.node_id:
                    value = val
                    break

        if value is None:
            raise Exception(f"ResultRef from node '{nr.node_id}' not found in store")

        if isinstance(value, list) and nr.output_index not in (0, None):
            try:
                value = value[nr.output_index]
            except IndexError:
                raise Exception(f"ResultRef index {nr.output_index} out of range for node '{nr.node_id}'")

        if nr.transform is not None:
            value = nr.transform(value)

        return value

    def _persist_result(self, store: DataStore, result):
        if result is None:
            return
        if isinstance(result, dict):
            for dtype, value in result.items():
                store.set(dtype, value, source=self)
            return

        if len(self.outputs) == 1:
            store.set(self.outputs[0], result, source=self)
            return

        if len(self.outputs) > 1:
            if not isinstance(result, (list, tuple)):
                raise TypeError(
                    f"{self.id or self.__class__.__name__} must return list/tuple for multiple outputs"
                )
            if len(result) != len(self.outputs):
                raise ValueError(
                    f"{self.id or self.__class__.__name__} returned {len(result)} values, expected {len(self.outputs)}"
                )
            for dtype, value in zip(self.outputs, result):
                store.set(dtype, value, source=self)

    async def _invoke_with_plugins(self, store: DataStore, args, kwargs):
        async def base_call():
            result = self.run(*args, **kwargs)
            if inspect.iscoroutine(result):
                return await result
            return result

        call_next = base_call
        for plugin in reversed(self.plugins):
            prev = call_next

            async def wrapped(plugin=plugin, prev=prev):
                return await self._run_plugin(plugin, prev, store)

            call_next = wrapped

        return await call_next()

    async def _run_plugin(self, plugin, call_next, store: DataStore):
        runner = getattr(plugin, "run", None)
        if runner is None and callable(plugin):
            runner = plugin
        if runner is None:
            raise TypeError(f"Plugin {plugin!r} must be callable or define run(...)")

        sig = inspect.signature(runner)
        argc = len(sig.parameters)

        if argc >= 3:
            outcome = runner(call_next, store, self)
        elif argc == 2:
            outcome = runner(call_next, store)
        elif argc == 1:
            outcome = runner(call_next)
        else:
            outcome = runner()

        if inspect.iscoroutine(outcome):
            return await outcome
        return outcome

    async def run(self, *args, **kwargs):
        raise NotImplementedError
