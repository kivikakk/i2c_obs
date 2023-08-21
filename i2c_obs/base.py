from pathlib import Path

__all__ = [
    "path",
]


def path(rest: str) -> Path:
    base = Path(__file__).parent.parent.absolute()
    return base / rest
