"""Unit tests for the local Neo4j Docker installer."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from download_install_neo4j_docker import Neo4jDockerInstaller


class Neo4jDockerInstallerTest(unittest.TestCase):
    """Validate installer logic without changing Docker or the project .env."""

    def test_generate_password_uses_requested_length(self) -> None:
        password = Neo4jDockerInstaller.generate_password(length=48)
        self.assertEqual(48, len(password))
        self.assertTrue(password.isalnum())

    def test_create_parse_and_validate_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment_path = Path(temporary_directory) / ".env"
            Neo4jDockerInstaller.create_environment_file(
                environment_path=environment_path
            )
            environment = Neo4jDockerInstaller.parse_environment_file(
                environment_path=environment_path
            )
            Neo4jDockerInstaller.validate_environment(environment=environment)
            self.assertEqual(
                environment["NEO4J_PASSWORD"],
                environment["NEO4J_AUTH"].split("/", 1)[1],
            )
            if os.name != "nt":
                self.assertEqual(0o600, environment_path.stat().st_mode & 0o777)

    def test_existing_environment_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment_path = Path(temporary_directory) / ".env"
            original_text = "EXISTING=value\n"
            environment_path.write_text(original_text, encoding="utf-8")
            Neo4jDockerInstaller.create_environment_file(
                environment_path=environment_path
            )
            self.assertEqual(original_text, environment_path.read_text(encoding="utf-8"))

    def test_validate_environment_rejects_password_mismatch(self) -> None:
        environment = {
            "NEO4J_AUTH": "neo4j/first_password",
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "second_password",
        }
        with self.assertRaisesRegex(RuntimeError, "must match NEO4J_PASSWORD"):
            Neo4jDockerInstaller.validate_environment(environment=environment)

    def test_validate_environment_rejects_placeholder(self) -> None:
        environment = {
            "NEO4J_AUTH": "neo4j/change_this_password",
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "change_this_password",
        }
        with self.assertRaisesRegex(RuntimeError, "placeholder"):
            Neo4jDockerInstaller.validate_environment(environment=environment)

    def test_compose_command_uses_explicit_environment_file(self) -> None:
        command = Neo4jDockerInstaller.compose_command(
            environment_path=Path("/project/.env"),
            arguments=["up", "-d", "neo4j"],
        )
        self.assertEqual(
            [
                "docker",
                "compose",
                "--env-file",
                "/project/.env",
                "up",
                "-d",
                "neo4j",
            ],
            command,
        )

    @patch.object(
        Neo4jDockerInstaller,
        "get_container_health",
        side_effect=["starting", "healthy"],
    )
    @patch("download_install_neo4j_docker.time.sleep")
    def test_wait_for_neo4j_returns_when_healthy(
        self, mocked_sleep, mocked_get_container_health
    ) -> None:
        Neo4jDockerInstaller.wait_for_neo4j(
            repository_root=Path("/project"), timeout_seconds=30
        )
        self.assertEqual(2, mocked_get_container_health.call_count)
        mocked_sleep.assert_called_once_with(2)

    @patch.object(
        Neo4jDockerInstaller,
        "get_container_health",
        return_value="unhealthy",
    )
    def test_wait_for_neo4j_reports_unhealthy_container(
        self, mocked_get_container_health
    ) -> None:
        with self.assertRaisesRegex(RuntimeError, "container state 'unhealthy'"):
            Neo4jDockerInstaller.wait_for_neo4j(
                repository_root=Path("/project"), timeout_seconds=30
            )
        mocked_get_container_health.assert_called_once()


if __name__ == "__main__":
    unittest.main()