class DataStore:
    def __init__(self):
        self._data = {}
        self._source = {}
        self._by_node = {}
        self._node_result = {}
        self._execution_context = None

    def set(self, dtype, value, source=None):
        # `dtype` (usually a class) acts as the typed data channel key.
        self._data[dtype] = value
        self._source[dtype] = source
        node_id = getattr(source, "id", None)
        if node_id:
            bucket = self._by_node.setdefault(node_id, {})
            bucket[dtype] = value

    def set_node_result(self, node_id, value):
        if node_id:
            self._node_result[node_id] = value

    def get_node_result(self, node_id):
        return self._node_result.get(node_id)

    def get(self, dtype):
        return self._data.get(dtype)

    def has(self, dtype):
        return dtype in self._data

    def get_from_node(self, node_id, output_type=None):
        # Node-scoped lookup is used by ResultRef(node_id=...).
        node_outputs = self._by_node.get(node_id, {})
        if output_type is not None:
            return node_outputs.get(output_type)
        for _, value in node_outputs.items():
            return value
        return None

    def merge(self, other, on_conflict="overwrite"):
        # Used by Parallel to fold branch stores into a single parent store.
        if on_conflict not in {"overwrite", "keep", "error"}:
            raise ValueError(f"Unsupported merge conflict policy: {on_conflict}")

        for dtype, value in other._data.items():
            if dtype in self._data:
                if on_conflict == "keep":
                    continue
                if on_conflict == "error" and self._data[dtype] != value:
                    raise ValueError(f"Data conflict on dtype '{dtype}' during parallel merge")

            source = other._source.get(dtype)
            self.set(dtype, value, source=source)
        for node_id, value in other._node_result.items():
            if node_id in self._node_result:
                if on_conflict == "keep":
                    continue
                if on_conflict == "error" and self._node_result[node_id] != value:
                    raise ValueError(f"Node result conflict on node '{node_id}' during parallel merge")
            self._node_result[node_id] = value

    def copy(self):
        new = DataStore()
        new._data = self._data.copy()
        new._source = self._source.copy()
        new._by_node = {node_id: bucket.copy() for node_id, bucket in self._by_node.items()}
        new._node_result = self._node_result.copy()
        new._execution_context = self._execution_context
        return new

    def attach_execution_context(self, context):
        # Kept on store so node execution path can emit events without new call signatures.
        self._execution_context = context

    def get_execution_context(self):
        return self._execution_context
