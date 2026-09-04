from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ContextLoaderError(RuntimeError):
    """Base exception for all ContextLoader operations and file resolution failures."""
    pass


class ContextNotFoundError(ContextLoaderError):
    """Raised when a requested context file does not exist."""
    pass


class ContextPathError(ContextLoaderError):
    """Raised when a path is invalid, absolute, or attempts to escape the root directory."""
    pass


class ContextLoader:
    """Safe, read-only repository context reader for agent memory and contracts."""

    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            self._root = ROOT
        else:
            self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        """The resolved base repository directory."""
        return self._root

    def resolve(self, relative_path: str | Path) -> Path:
        """Safely resolve a repository-relative path within the root directory.

        Raises:
            ContextPathError: If relative_path is empty, absolute, or escapes the root directory.
        """
        if not isinstance(relative_path, (str, Path)):
            raise ContextPathError(
                f"relative_path must be a str or Path, got {type(relative_path).__name__}"
            )

        path_str = str(relative_path).strip()
        if not path_str:
            raise ContextPathError("relative_path cannot be empty or whitespace.")

        raw_path = Path(relative_path)
        if raw_path.is_absolute() or path_str.startswith("/") or path_str.startswith("\\"):
            raise ContextPathError(f"Absolute paths are forbidden in ContextLoader: '{relative_path}'")

        if len(path_str) >= 2 and path_str[1] == ":":
            raise ContextPathError(f"Absolute drive-letter paths are forbidden: '{relative_path}'")

        target = (self._root / raw_path).resolve()

        try:
            target.relative_to(self._root.resolve())
        except ValueError:
            raise ContextPathError(
                f"Path traversal detected: '{relative_path}' escapes root '{self._root}'"
            )

        return target

    def load_text(self, relative_path: str | Path) -> str:
        """Load and return the raw, un-modified UTF-8 text content of a repository file.

        Raises:
            ContextPathError: If path resolution fails or escapes the root.
            ContextNotFoundError: If the file does not exist.
            ContextLoaderError: If target is a directory, not a file, or decoding fails.
        """
        target = self.resolve(relative_path)

        if not target.exists():
            raise ContextNotFoundError(f"Context file not found: '{relative_path}'")

        if not target.is_file():
            raise ContextLoaderError(f"Path is not a regular file: '{relative_path}'")

        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ContextLoaderError(
                f"Failed to decode file '{relative_path}' as UTF-8: {e}"
            ) from e
        except Exception as e:
            raise ContextLoaderError(
                f"Failed reading context file '{relative_path}': {e}"
            ) from e
