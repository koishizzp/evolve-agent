"""FASTA 文件读写与验证。"""

from pathlib import Path
from Bio import SeqIO


def validate_fasta(fasta_path: str) -> bool:
    """验证 FASTA 文件是否合法。"""
    path = Path(fasta_path)
    if not path.exists() or path.stat().st_size == 0:
        return False
    records = list(SeqIO.parse(path, "fasta"))
    return len(records) > 0 and all(str(record.seq).strip() for record in records)


def read_fasta(fasta_path: str) -> dict:
    """读取第一个 FASTA 记录并返回名称和序列。"""
    if not validate_fasta(fasta_path):
        raise ValueError(f"Invalid FASTA file: {fasta_path}")
    record = next(SeqIO.parse(fasta_path, "fasta"))
    return {"id": record.id, "description": record.description, "sequence": str(record.seq)}
