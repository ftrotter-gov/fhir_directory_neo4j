"""Tests for shared runtime environment and FHIR directory resolution."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from importers.runtime_config import resolve_fhir_directory  # noqa: E402
from import_or_update_ndjson import load_neo4j_config  # noqa: E402


class RuntimeConfigTest(unittest.TestCase):
    """Verify CLI and environment directory resolution precedence and errors."""

    def test_command_line_directory_overrides_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            command_line_directory = root / "command_line"
            environment_directory = root / "environment"
            command_line_directory.mkdir()
            environment_directory.mkdir()
            environment_path = root / ".env"
            environment_path.write_text(
                f"FHIR_DIRECTORY_PATH={environment_directory}\n", encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=True):
                result = resolve_fhir_directory(
                    command_line_directory=command_line_directory,
                    environment_path=environment_path,
                )
            self.assertEqual(command_line_directory.resolve(), result)

    def test_uses_directory_from_environment_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fhir_directory = root / "fhir"
            fhir_directory.mkdir()
            environment_path = root / ".env"
            environment_path.write_text(
                "FHIR_DIRECTORY_PATH=./fhir\n", encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=True):
                result = resolve_fhir_directory(
                    command_line_directory=None, environment_path=environment_path
                )
            self.assertEqual(fhir_directory.resolve(), result)

    def test_exported_environment_overrides_environment_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            exported_directory = root / "exported"
            file_directory = root / "file"
            exported_directory.mkdir()
            file_directory.mkdir()
            environment_path = root / ".env"
            environment_path.write_text(
                f"FHIR_DIRECTORY_PATH={file_directory}\n", encoding="utf-8"
            )
            with patch.dict(
                os.environ,
                {"FHIR_DIRECTORY_PATH": str(exported_directory)},
                clear=True,
            ):
                result = resolve_fhir_directory(
                    command_line_directory=None, environment_path=environment_path
                )
            self.assertEqual(exported_directory.resolve(), result)

    def test_rejects_missing_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment_path = Path(temporary_directory) / ".env"
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "No FHIR directory"):
                    resolve_fhir_directory(
                        command_line_directory=None,
                        environment_path=environment_path,
                    )

    def test_rejects_nonexistent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment_path = Path(temporary_directory) / ".env"
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "does not exist"):
                    resolve_fhir_directory(
                        command_line_directory=Path("missing"),
                        environment_path=environment_path,
                    )

    def test_rejects_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            file_path = root / "not_a_directory"
            file_path.write_text("FHIR", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "not a directory"):
                    resolve_fhir_directory(
                        command_line_directory=file_path,
                        environment_path=root / ".env",
                    )

    def test_neo4j_config_remains_available_after_environment_loading(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://example.test:7687",
                "NEO4J_USER": "example_user",
                "NEO4J_PASSWORD": "example_password",
            },
            clear=True,
        ):
            config = load_neo4j_config()
        self.assertEqual("bolt://example.test:7687", config["uri"])
        self.assertEqual("example_user", config["user"])
        self.assertEqual("example_password", config["password"])


if __name__ == "__main__":
    unittest.main()