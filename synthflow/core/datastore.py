class DataStore:
    def __init__(self):
        self._data = {}
        self._source = {}
        self._by_node = {}
        self._node_result = {}

    def set(self, dtype, value, source=None):
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
        node_outputs = self._by_node.get(node_id, {})
        if output_type is not None:
            return node_outputs.get(output_type)
        for _, value in node_outputs.items():
            return value
        return None

    def merge(self, other):
        for dtype, value in other._data.items():
            source = other._source.get(dtype)
            self.set(dtype, value, source=source)
        self._node_result.update(other._node_result)

    def copy(self):
        new = DataStore()
        new._data = self._data.copy()
        new._source = self._source.copy()
        new._by_node = {node_id: bucket.copy() for node_id, bucket in self._by_node.items()}
        new._node_result = self._node_result.copy()
        return new
