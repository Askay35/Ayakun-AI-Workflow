from abc import ABC, abstractmethod


class NodeAction(ABC):
    """Один тип узла → одно действие."""

    @abstractmethod
    async def execute(self, node: object, context: dict) -> object:
        raise NotImplementedError
