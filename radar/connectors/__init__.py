from .ashby import AshbyConnector
from .base import RawJob
from .greenhouse import GreenhouseConnector
from .gupy import GupyConnector
from .lever import LeverConnector

CONNECTORS_BY_PROVIDER = {
    "greenhouse": GreenhouseConnector(),
    "lever": LeverConnector(),
    "ashby": AshbyConnector(),
    "gupy": GupyConnector(),
}

__all__ = [
    "RawJob",
    "GreenhouseConnector",
    "LeverConnector",
    "AshbyConnector",
    "GupyConnector",
    "CONNECTORS_BY_PROVIDER",
]
