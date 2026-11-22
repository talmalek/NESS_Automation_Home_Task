from abc import ABC, abstractmethod

from Ammeters.client import request_current_from_ammeter
from src.utils.config import AmmeterConfig


class BaseAmmeterClient(ABC):
    """Abstract contract for any ammeter client (TCP, Serial, Modbus, Mock)."""

    def __init__(self, name: str, method: str = ""):
        self.name = name
        self.method = method

    @abstractmethod
    def read_current(self) -> float:
        """Read a single current measurement in Amperes."""
        raise NotImplementedError


class TcpAmmeterClient(BaseAmmeterClient):
    """Config-driven TCP client supporting all TCP ammeters with zero boilerplate."""

    def __init__(self, config: AmmeterConfig):
        super().__init__(name=config.name, method=config.method)
        self.config = config

    def read_current(self) -> float:
        value = request_current_from_ammeter(
            port=self.config.port,
            command=self.config.command,
            host=self.config.host,
            timeout=self.config.timeout_seconds,
            verbose=False,
        )
        if value is None:
            raise ValueError(f"No current value returned from ammeter '{self.name}'.")
        return float(value)
