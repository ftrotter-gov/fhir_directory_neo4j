#!/usr/bin/env python3
"""Install Python dependencies and start the project's Neo4j Docker service."""

import argparse
import os
import secrets
import shutil
import string
import subprocess
import sys
import time
import venv
from pathlib import Path
from typing import Dict, Optional, Sequence


class Neo4jDockerInstaller:
    """Organize the idempotent local development installation workflow."""

    CONTAINER_NAME = "fhir_neo4j_analysis"
    DEFAULT_TIMEOUT_SECONDS = 180
    MINIMUM_PYTHON = (3, 9)
    REQUIRED_ENVIRONMENT_KEYS = {
        "NEO4J_AUTH",
        "NEO4J_PASSWORD",
        "NEO4J_URI",
        "NEO4J_USER",
    }

    @staticmethod
    def repository_root() -> Path:
        """Return the repository directory containing this installer."""
        return Path(__file__).resolve().parent

    @staticmethod
    def virtual_environment_python(*, virtual_environment_directory: Path) -> Path:
        """Return the platform-specific Python executable inside a venv."""
        if os.name == "nt":
            return virtual_environment_directory / "Scripts" / "python.exe"
        return virtual_environment_directory / "bin" / "python"

    @staticmethod
    def is_running_in_virtual_environment(
        *, virtual_environment_directory: Path
    ) -> bool:
        """Return whether the current interpreter belongs to the project venv."""
        expected_prefix = virtual_environment_directory.resolve()
        return Path(sys.prefix).resolve() == expected_prefix

    @staticmethod
    def ensure_supported_python() -> None:
        """Stop with a useful message when Python is too old."""
        if sys.version_info < Neo4jDockerInstaller.MINIMUM_PYTHON:
            required_version = ".".join(
                str(part) for part in Neo4jDockerInstaller.MINIMUM_PYTHON
            )
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: "
                f"Python {required_version} or newer is required."
            )

    @staticmethod
    def ensure_virtual_environment(
        *, repository_root: Path, original_arguments: Sequence[str]
    ) -> None:
        """Create the project venv and restart this script inside it when needed."""
        virtual_environment_directory = repository_root / ".venv"
        virtual_environment_python = (
            Neo4jDockerInstaller.virtual_environment_python(
                virtual_environment_directory=virtual_environment_directory
            )
        )

        if not virtual_environment_python.exists():
            print(f"Creating Python virtual environment: {virtual_environment_directory}")
            venv.EnvBuilder(with_pip=True).create(virtual_environment_directory)

        if not Neo4jDockerInstaller.is_running_in_virtual_environment(
            virtual_environment_directory=virtual_environment_directory
        ):
            print("Restarting installer with the project virtual environment...")
            os.execv(
                str(virtual_environment_python),
                [str(virtual_environment_python), str(Path(__file__).resolve()), *original_arguments],
            )

    @staticmethod
    def run_command(
        *,
        command: Sequence[str],
        repository_root: Path,
        input_text: Optional[str] = None,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run one command and report failures with installer-specific context."""
        try:
            return subprocess.run(
                list(command),
                cwd=repository_root,
                input=input_text,
                text=True,
                check=True,
                capture_output=capture_output,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: "
                f"Required command was not found: {command[0]}"
            ) from error
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            detail_suffix = f" Details: {detail}" if detail else ""
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: Command failed: "
                f"{command[0]}.{detail_suffix}"
            ) from error

    @staticmethod
    def install_requirements(*, repository_root: Path) -> None:
        """Install all project dependencies with the active venv interpreter."""
        requirements_path = repository_root / "requirements.txt"
        if not requirements_path.is_file():
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: requirements.txt is missing."
            )
        print("Installing Python requirements into .venv...")
        Neo4jDockerInstaller.run_command(
            command=[
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(requirements_path),
            ],
            repository_root=repository_root,
        )

    @staticmethod
    def generate_password(*, length: int = 32) -> str:
        """Generate a Docker/Neo4j-safe random password."""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def create_environment_file(*, environment_path: Path) -> None:
        """Create a new environment file without exposing its generated password."""
        if environment_path.exists():
            return
        password = Neo4jDockerInstaller.generate_password()
        environment_text = (
            "# Generated by download_install_neo4j_docker.py. Do not commit this file.\n"
            f"NEO4J_AUTH=neo4j/{password}\n"
            "NEO4J_URI=bolt://localhost:7687\n"
            "NEO4J_USER=neo4j\n"
            f"NEO4J_PASSWORD={password}\n"
        )
        environment_path.write_text(environment_text, encoding="utf-8")
        try:
            environment_path.chmod(0o600)
        except OSError:
            # Some platforms do not implement POSIX permission semantics.
            pass
        print(f"Created {environment_path.name} with a generated Neo4j password.")

    @staticmethod
    def parse_environment_file(*, environment_path: Path) -> Dict[str, str]:
        """Parse simple KEY=VALUE settings without executing shell content."""
        if not environment_path.is_file():
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: .env does not exist."
            )
        environment: Dict[str, str] = {}
        for line_number, raw_line in enumerate(
            environment_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped_line = raw_line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue
            if "=" not in stripped_line:
                raise RuntimeError(
                    "download_install_neo4j_docker.py Error: "
                    f"Invalid .env entry on line {line_number}; expected KEY=VALUE."
                )
            key, value = stripped_line.split("=", 1)
            environment[key.strip()] = value.strip().strip('"').strip("'")
        return environment

    @staticmethod
    def validate_environment(*, environment: Dict[str, str]) -> None:
        """Validate credentials shared by Docker, its health check, and Python."""
        missing_keys = sorted(
            key
            for key in Neo4jDockerInstaller.REQUIRED_ENVIRONMENT_KEYS
            if not environment.get(key)
        )
        if missing_keys:
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: .env is missing: "
                + ", ".join(missing_keys)
            )

        neo4j_auth = environment["NEO4J_AUTH"]
        if "/" not in neo4j_auth:
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: "
                "NEO4J_AUTH must use the username/password format."
            )
        auth_user, auth_password = neo4j_auth.split("/", 1)
        if auth_user != environment["NEO4J_USER"]:
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: "
                "NEO4J_AUTH username must match NEO4J_USER."
            )
        if auth_password != environment["NEO4J_PASSWORD"]:
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: "
                "NEO4J_AUTH password must match NEO4J_PASSWORD."
            )
        if auth_password in {"change_this_password", "your_password_here"}:
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: "
                "Replace the placeholder Neo4j password in .env."
            )

    @staticmethod
    def validate_docker(*, repository_root: Path) -> None:
        """Confirm the Docker CLI, Compose plugin, and daemon are available."""
        if shutil.which("docker") is None:
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: Docker is not installed. "
                "Install Docker Desktop or Docker Engine and rerun this script."
            )
        Neo4jDockerInstaller.run_command(
            command=["docker", "compose", "version"],
            repository_root=repository_root,
            capture_output=True,
        )
        Neo4jDockerInstaller.run_command(
            command=["docker", "info"],
            repository_root=repository_root,
            capture_output=True,
        )

    @staticmethod
    def compose_command(*, environment_path: Path, arguments: Sequence[str]) -> list[str]:
        """Build a Docker Compose command that explicitly uses the project .env."""
        return [
            "docker",
            "compose",
            "--env-file",
            str(environment_path),
            *arguments,
        ]

    @staticmethod
    def start_neo4j(*, repository_root: Path, environment_path: Path) -> None:
        """Download the configured image and start the Neo4j service."""
        print("Downloading the Neo4j Docker image...")
        Neo4jDockerInstaller.run_command(
            command=Neo4jDockerInstaller.compose_command(
                environment_path=environment_path, arguments=["pull", "neo4j"]
            ),
            repository_root=repository_root,
        )
        print("Starting the Neo4j container...")
        Neo4jDockerInstaller.run_command(
            command=Neo4jDockerInstaller.compose_command(
                environment_path=environment_path, arguments=["up", "-d", "neo4j"]
            ),
            repository_root=repository_root,
        )

    @staticmethod
    def get_container_health(*, repository_root: Path) -> str:
        """Return Docker's health value, or a precise non-health state."""
        result = Neo4jDockerInstaller.run_command(
            command=[
                "docker",
                "inspect",
                "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
                Neo4jDockerInstaller.CONTAINER_NAME,
            ],
            repository_root=repository_root,
            capture_output=True,
        )
        return result.stdout.strip()

    @staticmethod
    def wait_for_neo4j(*, repository_root: Path, timeout_seconds: int) -> None:
        """Wait for the container health check with a bounded timeout."""
        print(f"Waiting up to {timeout_seconds} seconds for Neo4j to become healthy...")
        deadline = time.monotonic() + timeout_seconds
        last_health = "container health has not been reported"
        while time.monotonic() < deadline:
            last_health = Neo4jDockerInstaller.get_container_health(
                repository_root=repository_root
            )
            if last_health == "healthy":
                print("Neo4j is healthy.")
                return
            if last_health in {"exited", "dead", "unhealthy"}:
                break
            time.sleep(2)
        raise RuntimeError(
            "download_install_neo4j_docker.py Error: Neo4j did not become healthy "
            f"within {timeout_seconds} seconds (last status: {last_health}). "
            "Run 'docker compose logs neo4j' for details."
        )

    @staticmethod
    def apply_schema(
        *, repository_root: Path, environment: Dict[str, str]
    ) -> None:
        """Apply the idempotent Cypher schema inside the running container."""
        schema_path = repository_root / "schema" / "indexes.cypher"
        if not schema_path.is_file():
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: schema/indexes.cypher is missing."
            )
        print("Applying Neo4j constraints and indexes...")
        Neo4jDockerInstaller.run_command(
            command=[
                "docker",
                "exec",
                "-i",
                Neo4jDockerInstaller.CONTAINER_NAME,
                "cypher-shell",
                "-u",
                environment["NEO4J_USER"],
                "-p",
                environment["NEO4J_PASSWORD"],
            ],
            repository_root=repository_root,
            input_text=schema_path.read_text(encoding="utf-8"),
            capture_output=True,
        )

    @staticmethod
    def verify_installation(
        *, repository_root: Path, environment: Dict[str, str]
    ) -> None:
        """Verify Cypher access and imports from the active venv."""
        Neo4jDockerInstaller.run_command(
            command=[
                "docker",
                "exec",
                Neo4jDockerInstaller.CONTAINER_NAME,
                "cypher-shell",
                "-u",
                environment["NEO4J_USER"],
                "-p",
                environment["NEO4J_PASSWORD"],
                "RETURN 1;",
            ],
            repository_root=repository_root,
            capture_output=True,
        )
        Neo4jDockerInstaller.run_command(
            command=[sys.executable, "-c", "import duckdb; import neo4j"],
            repository_root=repository_root,
            capture_output=True,
        )

    @staticmethod
    def build_argument_parser() -> argparse.ArgumentParser:
        """Build the installer command-line parser."""
        parser = argparse.ArgumentParser(
            description=(
                "Create .venv, install requirements, configure credentials, "
                "start Neo4j in Docker, and apply the graph schema."
            )
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=Neo4jDockerInstaller.DEFAULT_TIMEOUT_SECONDS,
            help="Seconds to wait for Neo4j health (default: 180)",
        )
        return parser

    @staticmethod
    def main(*, arguments: Optional[Sequence[str]] = None) -> int:
        """Run the complete installation workflow."""
        original_arguments = list(arguments if arguments is not None else sys.argv[1:])
        parsed_arguments = Neo4jDockerInstaller.build_argument_parser().parse_args(
            original_arguments
        )
        if parsed_arguments.timeout <= 0:
            raise RuntimeError(
                "download_install_neo4j_docker.py Error: --timeout must be positive."
            )

        Neo4jDockerInstaller.ensure_supported_python()
        repository_root = Neo4jDockerInstaller.repository_root()
        Neo4jDockerInstaller.ensure_virtual_environment(
            repository_root=repository_root, original_arguments=original_arguments
        )
        Neo4jDockerInstaller.install_requirements(repository_root=repository_root)

        environment_path = repository_root / ".env"
        Neo4jDockerInstaller.create_environment_file(
            environment_path=environment_path
        )
        environment = Neo4jDockerInstaller.parse_environment_file(
            environment_path=environment_path
        )
        Neo4jDockerInstaller.validate_environment(environment=environment)

        Neo4jDockerInstaller.validate_docker(repository_root=repository_root)
        Neo4jDockerInstaller.start_neo4j(
            repository_root=repository_root, environment_path=environment_path
        )
        Neo4jDockerInstaller.wait_for_neo4j(
            repository_root=repository_root,
            timeout_seconds=parsed_arguments.timeout,
        )
        Neo4jDockerInstaller.apply_schema(
            repository_root=repository_root, environment=environment
        )
        Neo4jDockerInstaller.verify_installation(
            repository_root=repository_root, environment=environment
        )

        activation_path = ".venv\\Scripts\\activate" if os.name == "nt" else ".venv/bin/activate"
        print("\nInstallation complete.")
        print("Neo4j Browser: http://localhost:7474")
        print(f"Bolt URI: {environment['NEO4J_URI']}")
        print(f"Activate the project environment: source {activation_path}")
        print("Safe import: python scripts/import_or_update_ndjson.py /path/to/data")
        print("Empty database only: python scripts/import_ndjson_fast.py /path/to/data")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(Neo4jDockerInstaller.main())
    except RuntimeError as installer_error:
        print(installer_error, file=sys.stderr)
        raise SystemExit(1)