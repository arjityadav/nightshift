from pydantic import BaseModel, Field


class ChaosConfig(BaseModel):
    error_rate: float = Field(0, ge=0, le=1)
    latency_ms: int = Field(0, ge=0, le=10000)
    leak_kb_per_request: int = Field(0, ge=0, le=10240)


class ChaosStatus(ChaosConfig):
    """What GET/PUT/DELETE /chaos return: the settings plus how much memory has leaked."""

    leaked_kb: int


class Chaos:
    """The current chaos state of one app."""

    def __init__(self) -> None:
        self.config = ChaosConfig()
        self.leaked: list[bytes] = []

    def status(self) -> ChaosStatus:
        leaked_kb = sum(len(b) for b in self.leaked) // 1024
        return ChaosStatus(**self.config.model_dump(), leaked_kb=leaked_kb)


class ChaosError(Exception):
    """Exception raised when chaos is injected."""
