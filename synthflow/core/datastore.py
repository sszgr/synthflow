class DataStore:
    def __init__(self):
        self._data = {}
        self._source = {}

    def set(self, dtype, value, source=None):
        self._data[dtype] = value
        self._source[dtype] = source

    def get(self, dtype):
        return self._data.get(dtype)

    def has(self, dtype):
        return dtype in self._data

    def copy(self):
        new = DataStore()
        new._data = self._data.copy()
        new._source = self._source.copy()
        return new
