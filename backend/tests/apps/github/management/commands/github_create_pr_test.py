"""Tests for the GitHub PR creation command."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase
from github.GithubException import BadCredentialsException, GithubException

from apps.github.management.commands.github_create_pr import Command


class TestGitHubCreatePRCommand(TestCase):
    """Test cases for the GitHub PR creation command."""

    def setUp(self):
        """Set up test fixtures."""
        self.command = Command()
        self.command.stdout = MagicMock()
        self.command.stderr = MagicMock()

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_success(self, mock_get_github_client):
        """Test successful PR creation."""
        # Mock GitHub client and repository
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_base_branch = MagicMock()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/OWASP/Nest/pull/123"
        mock_pr.number = 123

        mock_get_github_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_branch.return_value = mock_base_branch
        mock_repo.create_pull.return_value = mock_pr

        # Call command
        call_command(
            "github_create_pr",
            "--repository=OWASP/Nest",
            "--title=Test PR",
            "--body=Test description",
            "--head-branch=feature/test",
        )

        # Verify calls
        mock_gh.get_repo.assert_called_once_with("OWASP/Nest")
        mock_repo.get_branch.assert_called_once_with("main")
        mock_repo.create_pull.assert_called_once_with(
            title="Test PR",
            body="Test description",
            base="main",
            head="feature/test",
            draft=False,
        )
        mock_gh.close.assert_called_once()

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_with_files(self, mock_get_github_client):
        """Test PR creation with file uploads."""
        # Create temporary test files
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1:
            f1.write("Hello World")
            temp_file1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f2:
            f2.write("def test_function():\n    return 'test'")
            temp_file2 = f2.name

        try:
            # Mock GitHub client and repository
            mock_gh = MagicMock()
            mock_repo = MagicMock()
            mock_base_branch = MagicMock()
            mock_base_branch.commit.sha = "abc123"
            mock_pr = MagicMock()
            mock_pr.html_url = "https://github.com/OWASP/Nest/pull/123"

            mock_get_github_client.return_value = mock_gh
            mock_gh.get_repo.return_value = mock_repo
            mock_repo.get_branch.return_value = mock_base_branch
            mock_repo.create_pull.return_value = mock_pr
            mock_repo.create_git_ref.return_value = None
            mock_repo.create_file.return_value = None

            # Call command with files
            call_command(
                "github_create_pr",
                "--repository=OWASP/Nest",
                "--title=Test PR",
                "--body=Test description",
                "--head-branch=feature/test",
                f"--files={temp_file1}:test.txt,{temp_file2}:src/test.py",
            )

            # Verify file creation
            mock_repo.create_git_ref.assert_called_once_with("refs/heads/feature/test", "abc123")
            # Verify both files were created
            assert mock_repo.create_file.call_count == 2

        finally:
            # Clean up temporary files
            Path(temp_file1).unlink(missing_ok=True)
            Path(temp_file2).unlink(missing_ok=True)

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_with_labels_assignees_reviewers(self, mock_get_github_client):
        """Test PR creation with labels, assignees, and reviewers."""
        # Mock GitHub client and repository
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_base_branch = MagicMock()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/OWASP/Nest/pull/123"

        mock_get_github_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_branch.return_value = mock_base_branch
        mock_repo.create_pull.return_value = mock_pr

        # Call command with labels, assignees, and reviewers
        call_command(
            "github_create_pr",
            "--repository=OWASP/Nest",
            "--title=Test PR",
            "--body=Test description",
            "--head-branch=feature/test",
            "--labels=bug,enhancement",
            "--assignees=user1,user2",
            "--reviewers=reviewer1,reviewer2",
        )

        # Verify calls
        mock_pr.add_to_labels.assert_called_once_with("bug", "enhancement")
        mock_pr.add_to_assignees.assert_called_once_with("user1", "user2")
        mock_pr.add_to_reviewers.assert_called_once_with("reviewer1", "reviewer2")

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_draft_pr(self, mock_get_github_client):
        """Test creating a draft PR."""
        # Mock GitHub client and repository
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_base_branch = MagicMock()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/OWASP/Nest/pull/123"

        mock_get_github_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_branch.return_value = mock_base_branch
        mock_repo.create_pull.return_value = mock_pr

        # Call command with draft flag
        call_command(
            "github_create_pr",
            "--repository=OWASP/Nest",
            "--title=Test PR",
            "--body=Test description",
            "--head-branch=feature/test",
            "--draft",
        )

        # Verify draft PR creation
        mock_repo.create_pull.assert_called_once_with(
            title="Test PR",
            body="Test description",
            base="main",
            head="feature/test",
            draft=True,
        )

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_dry_run(self, mock_get_github_client):
        """Test dry-run mode."""
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_file = f.name

        try:
            # Mock GitHub client and repository
            mock_gh = MagicMock()
            mock_repo = MagicMock()
            mock_base_branch = MagicMock()

            mock_get_github_client.return_value = mock_gh
            mock_gh.get_repo.return_value = mock_repo
            mock_repo.get_branch.return_value = mock_base_branch

            # Call command with dry-run flag
            call_command(
                "github_create_pr",
                "--repository=OWASP/Nest",
                "--title=Test PR",
                "--body=Test description",
                "--head-branch=feature/test",
                f"--files={temp_file}:test.txt",
                "--labels=bug",
                "--assignees=user1",
                "--reviewers=reviewer1",
                "--draft",
                "--dry-run",
            )

            # Verify no actual API calls were made
            mock_repo.create_pull.assert_not_called()
            mock_repo.create_file.assert_not_called()

            # Verify dry-run output
            self.command.stdout.write.assert_any_call(
                self.command.style.WARNING("DRY RUN - No changes will be made")
            )

        finally:
            # Clean up temporary file
            Path(temp_file).unlink(missing_ok=True)

    def test_parse_files_valid(self):
        """Test parsing valid files string."""
        files_str = "file1.txt:remote1.txt,file2.txt:remote2.txt"
        result = self.command._parse_files(files_str)
        expected = {"file1.txt": "remote1.txt", "file2.txt": "remote2.txt"}
        self.assertEqual(result, expected)

    def test_parse_files_empty(self):
        """Test parsing empty files string."""
        result = self.command._parse_files(None)
        self.assertEqual(result, {})

        result = self.command._parse_files("")
        self.assertEqual(result, {})

    def test_parse_files_invalid_format(self):
        """Test parsing invalid files string."""
        with self.assertRaises(SystemExit):
            self.command._parse_files("invalid_format")

    def test_parse_files_empty_paths(self):
        """Test parsing files string with empty paths."""
        with self.assertRaises(SystemExit):
            self.command._parse_files(":remote.txt")

        with self.assertRaises(SystemExit):
            self.command._parse_files("local.txt:")

    def test_validate_file_path_valid(self):
        """Test validating a valid file path."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_file = f.name

        try:
            result = self.command._validate_file_path(temp_file)
            self.assertEqual(result, Path(temp_file))
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_validate_file_path_nonexistent(self):
        """Test validating a nonexistent file path."""
        with self.assertRaises(SystemExit):
            self.command._validate_file_path("nonexistent_file.txt")

    def test_validate_file_path_directory(self):
        """Test validating a directory path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(SystemExit):
                self.command._validate_file_path(temp_dir)

    def test_read_file_content_valid(self):
        """Test reading file content."""
        # Create a temporary file with UTF-8 content
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as f:
            f.write("Hello World\nTest content")
            temp_file = f.name

        try:
            file_path = Path(temp_file)
            result = self.command._read_file_content(file_path)
            self.assertEqual(result, "Hello World\nTest content")
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_read_file_content_binary(self):
        """Test reading binary file content."""
        # Create a temporary file with binary content
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"Binary content with \x00\x01\x02")
            temp_file = f.name

        try:
            file_path = Path(temp_file)
            result = self.command._read_file_content(file_path)
            # Should handle binary content gracefully
            self.assertIn("Binary content", result)
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_parse_list_valid(self):
        """Test parsing valid list string."""
        list_str = "item1,item2,item3"
        result = self.command._parse_list(list_str)
        expected = ["item1", "item2", "item3"]
        self.assertEqual(result, expected)

    def test_parse_list_empty(self):
        """Test parsing empty list string."""
        result = self.command._parse_list(None)
        self.assertEqual(result, [])

        result = self.command._parse_list("")
        self.assertEqual(result, [])

    def test_parse_list_with_spaces(self):
        """Test parsing list string with spaces."""
        list_str = " item1 , item2 , item3 "
        result = self.command._parse_list(list_str)
        expected = ["item1", "item2", "item3"]
        self.assertEqual(result, expected)

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_invalid_repository_format(self, mock_get_github_client):
        """Test handling invalid repository format."""
        with self.assertRaises(SystemExit):
            call_command(
                "github_create_pr",
                "--repository=invalid-repo",
                "--title=Test PR",
                "--body=Test description",
                "--head-branch=feature/test",
            )

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_authentication_error(self, mock_get_github_client):
        """Test handling authentication error."""
        mock_get_github_client.side_effect = BadCredentialsException(401, "Bad credentials", None)

        with self.assertRaises(SystemExit):
            call_command(
                "github_create_pr",
                "--repository=OWASP/Nest",
                "--title=Test PR",
                "--body=Test description",
                "--head-branch=feature/test",
            )

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_repository_not_found(self, mock_get_github_client):
        """Test handling repository not found error."""
        mock_gh = MagicMock()
        mock_get_github_client.return_value = mock_gh
        mock_gh.get_repo.side_effect = GithubException(404, "Not Found", None)

        with self.assertRaises(SystemExit):
            call_command(
                "github_create_pr",
                "--repository=OWASP/NonExistent",
                "--title=Test PR",
                "--body=Test description",
                "--head-branch=feature/test",
            )

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_base_branch_not_found(self, mock_get_github_client):
        """Test handling base branch not found error."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_get_github_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_branch.side_effect = GithubException(404, "Branch not found", None)

        with self.assertRaises(SystemExit):
            call_command(
                "github_create_pr",
                "--repository=OWASP/Nest",
                "--title=Test PR",
                "--body=Test description",
                "--head-branch=feature/test",
                "--base-branch=non-existent",
            )

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_pr_creation_error(self, mock_get_github_client):
        """Test handling PR creation error."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_base_branch = MagicMock()
        mock_get_github_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_branch.return_value = mock_base_branch
        mock_repo.create_pull.side_effect = GithubException(422, "Validation failed", None)

        with self.assertRaises(SystemExit):
            call_command(
                "github_create_pr",
                "--repository=OWASP/Nest",
                "--title=Test PR",
                "--body=Test description",
                "--head-branch=feature/test",
            )

    @patch(
        "apps.github.management.commands.github_create_pr.get_github_client_with_installation_token"
    )
    def test_handle_file_upload_error(self, mock_get_github_client):
        """Test handling file upload error."""
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_file = f.name

        try:
            mock_gh = MagicMock()
            mock_repo = MagicMock()
            mock_base_branch = MagicMock()
            mock_base_branch.commit.sha = "abc123"
            mock_get_github_client.return_value = mock_gh
            mock_gh.get_repo.return_value = mock_repo
            mock_repo.get_branch.return_value = mock_base_branch
            mock_repo.create_git_ref.return_value = None
            mock_repo.create_file.side_effect = GithubException(422, "File upload failed", None)

            with self.assertRaises(SystemExit):
                call_command(
                    "github_create_pr",
                    "--repository=OWASP/Nest",
                    "--title=Test PR",
                    "--body=Test description",
                    "--head-branch=feature/test",
                    f"--files={temp_file}:test.txt",
                )

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_show_dry_run(self):
        """Test dry-run output."""
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_file = f.name

        try:
            self.command._show_dry_run(
                repository="OWASP/Nest",
                title="Test PR",
                body="Test description",
                base_branch="main",
                head_branch="feature/test",
                files={temp_file: "test.txt"},
                labels=["bug", "enhancement"],
                assignees=["user1"],
                reviewers=["reviewer1"],
                draft=True,
            )

            # Verify dry-run output calls
            self.command.stdout.write.assert_any_call(
                self.command.style.WARNING("DRY RUN - No changes will be made")
            )
            self.command.stdout.write.assert_any_call("Repository: OWASP/Nest")
            self.command.stdout.write.assert_any_call("Title: Test PR")
            self.command.stdout.write.assert_any_call("Body: Test description")
            self.command.stdout.write.assert_any_call("Base branch: main")
            self.command.stdout.write.assert_any_call("Head branch: feature/test")
            self.command.stdout.write.assert_any_call("Draft: True")
            self.command.stdout.write.assert_any_call("Files to upload:")
            self.command.stdout.write.assert_any_call("Labels: bug, enhancement")
            self.command.stdout.write.assert_any_call("Assignees: user1")
            self.command.stdout.write.assert_any_call("Reviewers: reviewer1")

        finally:
            Path(temp_file).unlink(missing_ok=True)
