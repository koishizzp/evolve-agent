from pathlib import Path

from Bio import SeqIO


def validate_fasta(fasta_path: str) -> bool:
    """Return True when the FASTA file exists and contains at least one sequence."""
    path = Path(fasta_path)
    if not path.exists() or path.stat().st_size == 0:
        return False
    records = list(SeqIO.parse(path, "fasta"))
    return len(records) > 0 and all(str(record.seq).strip() for record in records)


def read_fasta(fasta_path: str) -> dict:
    """Read the first FASTA record and return id, description, and sequence."""
    if not validate_fasta(fasta_path):
        raise ValueError(f"Invalid FASTA file: {fasta_path}")
    record = next(SeqIO.parse(fasta_path, "fasta"))
    return {"id": record.id, "description": record.description, "sequence": str(record.seq)}
