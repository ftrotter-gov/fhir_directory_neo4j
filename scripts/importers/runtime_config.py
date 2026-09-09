"""Shared runtime environment loading and FHIR source-directory resolution."""

import os
from pathlib import Path
from typing import Optional


def load_environment_file(*, environment_path: Path) -> None:
    """Load simple KEY=VALUE settings without overriding exported variables."""
    if not environment_path.is_file():
        return
    for raw_line in environment_path.read_text(encoding="utf-8").splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
            continue
        key, value = stripped_line.split("=", 1)
        os.environ.setdefault(
            key.strip(), value.strip().strip('"').strip("'")
        )


def resolve_fhir_directory(
    *, command_line_directory: Optional[Path], environment_path: Path
) -> Path:
    """Resolve CLI override, then FHIR_DIRECTORY_PATH from environment or .env."""
    load_environment_file(environment_path=environment_path)
    configured_directory = (
        str(command_line_directory)
        if command_line_directory is not None
        else os.getenv("FHIR_DIRECTORY_PATH", "").strip()
    )
    if not configured_directory:
        raise RuntimeError(
            "runtime_config.py Error: No FHIR directory was provided. Pass a "
            "directory argument or set FHIR_DIRECTORY_PATH in .env."
        )
    resolved_directory = Path(configured_directory).expanduser()
    if not resolved_directory.is_absolute():
        resolved_directory = (environment_path.parent / resolved_directory).resolve()
    else:
        resolved_directory = resolved_directory.resolve()
    if not resolved_directory.exists():
        raise RuntimeError(
            "runtime_config.py Error: FHIR directory does not exist: "
            f"{resolved_directory}"
        )
    if not resolved_directory.is_dir():
        raise RuntimeError(
            "runtime_config.py Error: FHIR directory path is not a directory: "
            f"{resolved_directory}"
        )
    return resolved_directory