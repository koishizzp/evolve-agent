"""evolve-agent package."""

__all__ = ["EvolveAgent"]


def __getattr__(name: str):
    if name == "EvolveAgent":
        from .agent import EvolveAgent

        return EvolveAgent
    raise AttributeError(name)
