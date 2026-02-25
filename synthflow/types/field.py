class Field:
    def __init__(self, type_, required=True):
        self.type_ = type_
        self.required = required


def validate_params(schema, params):
    for name, field in schema.items():
        if field.required and name not in params:
            raise ValueError(f"Missing parameter: {name}")

        if name in params and not isinstance(params[name], field.type_):
            raise TypeError(
                f"Parameter {name} must be {field.type_}"
            )
