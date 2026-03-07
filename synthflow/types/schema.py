from synthflow.types.field import Field


class Schema(dict):
    """Lightweight named schema wrapper.

    Accepts keyword arguments where values are `Field` definitions.
    Example: Schema(user_id=Field(int), name=Field(str, required=False))
    """

    def __init__(self, **fields):
        for name, field in fields.items():
            if not isinstance(field, Field):
                raise TypeError(f"Schema field '{name}' must be a Field instance")
        super().__init__(fields)
