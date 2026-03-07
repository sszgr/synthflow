from synthflow.types.field import Field, validate_params


def validate_node_params(node, params):
    schema = getattr(node, "params_schema", None)
    if not schema:
        return
    validate_params(schema, params)


def validate_node_output(node, result):
    schema = getattr(node, "output_schema", None)
    if schema is None:
        return

    if isinstance(schema, Field):
        _validate_field_value(schema=schema, value=result, path="return")
        return

    if isinstance(schema, dict):
        if not isinstance(result, dict):
            raise TypeError(
                f"{node.id or node.__class__.__name__} output must be dict for dict output_schema"
            )
        validate_params(schema, result)
        return

    if isinstance(schema, (list, tuple)):
        if not isinstance(result, (list, tuple)):
            raise TypeError(
                f"{node.id or node.__class__.__name__} output must be list/tuple for sequence output_schema"
            )
        if len(result) != len(schema):
            raise ValueError(
                f"{node.id or node.__class__.__name__} output size {len(result)} "
                f"does not match output_schema size {len(schema)}"
            )
        for index, (field_schema, value) in enumerate(zip(schema, result)):
            if not isinstance(field_schema, Field):
                raise TypeError("Sequence output_schema entries must be Field instances")
            _validate_field_value(field_schema, value, path=f"return[{index}]")
        return

    raise TypeError("output_schema must be Field, dict[str, Field], or sequence[Field]")


def _validate_field_value(schema: Field, value, path: str):
    if value is None and schema.required:
        raise ValueError(f"Missing required value for {path}")
    if value is not None and not isinstance(value, schema.type_):
        raise TypeError(f"{path} must be {schema.type_}")
