"""Two throwaway tools for Session 2: they only read the practice/ folder."""

from pathlib import Path

PRACTICE_ROOT = Path(__file__).resolve().parent.parent / "practice"


def safe_path(path: str) -> Path | None:
    """Resolve a path inside practice/, or None if it points outside it."""
    full = (PRACTICE_ROOT / path).resolve()
    return full if full.is_relative_to(PRACTICE_ROOT) else None


def count_lines(path: str) -> int:
    """Return the number of lines in one file under practice/ (path like 'app/main.py')."""
    full = safe_path(path)
    if full is None or not full.is_file():
        return -1  # S2 keeps it simple; S4 turns this into a proper error result
    return len(full.read_text().splitlines())


def list_directory(path: str = ".") -> list[str]:
    """List the files and folders in one folder under practice/ ('.' is the top)."""
    full = safe_path(path)
    if full is None or not full.is_dir():
        return []
    return sorted(p.name + ("/" if p.is_dir() else "") for p in full.iterdir())
