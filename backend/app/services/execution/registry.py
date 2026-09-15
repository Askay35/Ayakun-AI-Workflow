from collections.abc import Awaitable, Callable

Executor = Callable[[object, dict], Awaitable[object]]


class NodeRegistry:
    """type узла → async executor(node, context) -> output."""

    def __init__(self):
        self._executors: dict[str, Executor] = {}

    def register(self, node_type: str, executor: Executor) -> None:
        self._executors[node_type] = executor

    async def execute(self, node: object, context: dict) -> object:
        executor = self._executors.get(getattr(node, "type"))
        if not executor:
            raise ValueError(f"Нет executor для {getattr(node, 'type')}")
        return await executor(node, context)
