"""Utility exports."""

from .logger import setup_logger

__all__ = ["read_fasta", "validate_fasta", "setup_logger"]


def __getattr__(name: str):
    if name in {"read_fasta", "validate_fasta"}:
        from .fasta_utils import read_fasta, validate_fasta

        return {"read_fasta": read_fasta, "validate_fasta": validate_fasta}[name]
    raise AttributeError(name)
