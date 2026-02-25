from synthflow.core.condition import IF, OR, SWITCH, If, Switch
from synthflow.core.flow import Flow
from synthflow.core.node import ResultRef
from synthflow.core.parallel import Parallel


def PARALLEL(*nodes, id=None):
    return Parallel(*nodes, id=id)


__all__ = [
    "Flow",
    "IF",
    "OR",
    "PARALLEL",
    "SWITCH",
    "If",
    "Switch",
    "Parallel",
    "ResultRef",
]
