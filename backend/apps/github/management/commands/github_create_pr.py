"""A command to create Pull Requests on behalf of the OWASP Nest GitHub application."""

import logging
import sys
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand
from github.GithubException import BadCredentialsException, GithubException

from apps.github.auth import get_github_client_with_installation_token

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Create Pull Requests using GitHub App authentication."""

    help = "Create Pull Requests on behalf of the OWASP Nest GitHub application."

    def add_arguments(self, parser) -> None:
        """Add command-line arguments to the parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser instance.

        """
        parser.add_argument(
            "--repository",
            type=str,
            required=True,
            help="Repository in format 'owner/repo' (e.g., 'OWASP/Nest')",
        )
        parser.add_argument(
            "--title",
            type=str,
            required=True,
            help="Pull Request title",
        )
        parser.add_argument(
            "--body",
            type=str,
            required=True,
            help="Pull Request description",
        )
        parser.add_argument(
            "--base-branch",
            type=str,
            default="main",
            help="Base branch for the PR (default: main)",
        )
        parser.add_argument(
            "--head-branch",
            type=str,
            required=True,
            help="Head branch for the PR (e.g., 'feature/automated-update')",
        )
        parser.add_argument(
            "--files",
            type=str,
            help="Files to upload in format 'local_path:remote_path,local_path2:remote_path2'",
        )
        parser.add_argument(
            "--labels",
            type=str,
            help="Comma-separated list of labels to add to the PR",
        )
        parser.add_argument(
            "--assignees",
            type=str,
            help="Comma-separated list of assignees (GitHub usernames)",
        )
        parser.add_argument(
            "--reviewers",
            type=str,
            help="Comma-separated list of reviewers (GitHub usernames)",
        )
        parser.add_argument(
            "--draft",
            action="store_true",
            help="Create the PR as a draft",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually creating the PR",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Handle the command execution.

        Args:
            *args: Variable length argument list.
            **options: Arbitrary keyword arguments containing command options.

        """
        try:
            # Parse repository
            repository = options["repository"]
            if "/" not in repository:
                self.stderr.write(
                    self.style.ERROR(
                        f"Invalid repository format: {repository}. Expected format: 'owner/repo'"
                    )
                )
                sys.exit(1)

            owner, repo_name = repository.split("/", 1)

            # Get GitHub client with installation access token for PR creation
            gh = get_github_client_with_installation_token()
            logger.info("Successfully authenticated with GitHub using installation access token")

            # Get repository
            try:
                repo = gh.get_repo(repository)
                logger.info(f"Found repository: {repo.full_name}")
            except GithubException as e:
                self.stderr.write(
                    self.style.ERROR(f"Failed to access repository {repository}: {e}")
                )
                sys.exit(1)

            # Check if base branch exists
            try:
                base_branch = repo.get_branch(options["base_branch"])
                logger.info(f"Base branch '{base_branch.name}' exists")
            except GithubException as e:
                self.stderr.write(
                    self.style.ERROR(f"Base branch '{options['base_branch']}' not found: {e}")
                )
                sys.exit(1)

            # Parse files if provided
            files_to_upload = self._parse_files(options.get("files"))

            # Parse lists
            labels = self._parse_list(options.get("labels"))
            assignees = self._parse_list(options.get("assignees"))
            reviewers = self._parse_list(options.get("reviewers"))

            if options["dry_run"]:
                self._show_dry_run(
                    repository=repository,
                    title=options["title"],
                    body=options["body"],
                    base_branch=options["base_branch"],
                    head_branch=options["head_branch"],
                    files=files_to_upload,
                    labels=labels,
                    assignees=assignees,
                    reviewers=reviewers,
                    draft=options["draft"],
                )
                return

            # Upload files
            if files_to_upload:
                self._upload_files(repo, options["head_branch"], files_to_upload)

            # Create pull request
            pr = self._create_pull_request(
                repo=repo,
                title=options["title"],
                body=options["body"],
                base_branch=options["base_branch"],
                head_branch=options["head_branch"],
                draft=options["draft"],
            )

            # Add labels
            if labels:
                self._add_labels(pr, labels)

            # Add assignees
            if assignees:
                self._add_assignees(pr, assignees)

            # Add reviewers
            if reviewers:
                self._add_reviewers(pr, reviewers)

            self.stdout.write(
                self.style.SUCCESS(f"Successfully created Pull Request: {pr.html_url}")
            )

        except BadCredentialsException:
            self.stderr.write(
                self.style.ERROR(
                    "GitHub authentication failed. Please check your GitHub App configuration."
                )
            )
            sys.exit(1)
        except Exception as e:
            logger.exception("Unexpected error creating Pull Request")
            self.stderr.write(self.style.ERROR(f"Unexpected error: {e}"))
            sys.exit(1)
        finally:
            if "gh" in locals():
                gh.close()

    def _parse_files(self, files_str: str | None) -> dict[str, str]:
        """Parse files string into a dictionary mapping local paths to remote paths.

        Args:
            files_str: String in format 'local_path:remote_path,local_path2:remote_path2'

        Returns:
            Dictionary mapping local file paths to remote file paths.

        """
        if not files_str:
            return {}

        files = {}
        for file_spec in files_str.split(","):
            if ":" not in file_spec:
                self.stderr.write(
                    self.style.ERROR(
                        f"Invalid file specification: {file_spec}. "
                        "Expected format: 'local_path:remote_path'"
                    )
                )
                sys.exit(1)

            local_path, remote_path = file_spec.split(":", 1)
            local_path = local_path.strip()
            remote_path = remote_path.strip()

            # Validate local path
            if not local_path:
                self.stderr.write(
                    self.style.ERROR(f"Empty local path in specification: {file_spec}")
                )
                sys.exit(1)

            # Validate remote path
            if not remote_path:
                self.stderr.write(
                    self.style.ERROR(f"Empty remote path in specification: {file_spec}")
                )
                sys.exit(1)

            files[local_path] = remote_path

        return files

    def _parse_list(self, list_str: str | None) -> list[str]:
        """Parse comma-separated string into a list.

        Args:
            list_str: Comma-separated string

        Returns:
            List of strings.

        """
        if not list_str:
            return []

        return [item.strip() for item in list_str.split(",") if item.strip()]

    def _validate_file_path(self, file_path: str) -> Path:
        """Validate and return a Path object for the given file path.

        Args:
            file_path: Path to the file

        Returns:
            Path object for the file

        Raises:
            SystemExit: If the file path is invalid or file doesn't exist

        """
        try:
            path = Path(file_path)

            # Check if path is absolute or relative to current directory
            if not path.is_absolute():
                path = Path.cwd() / path

            # Validate the file exists
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
                sys.exit(1)

            # Validate it's a file, not a directory
            if not path.is_file():
                self.stderr.write(self.style.ERROR(f"Path is not a file: {file_path}"))
                sys.exit(1)

            # Check file size (limit to 100MB to prevent abuse)
            file_size = path.stat().st_size
            max_size = 100 * 1024 * 1024  # 100MB
            if file_size > max_size:
                self.stderr.write(
                    self.style.ERROR(
                        f"File too large: {file_path} ({file_size} bytes). "
                        f"Maximum size is {max_size} bytes."
                    )
                )
                sys.exit(1)

            return path

        except (OSError, ValueError) as e:
            self.stderr.write(self.style.ERROR(f"Invalid file path '{file_path}': {e}"))
            sys.exit(1)

    def _read_file_content(self, file_path: Path) -> str:
        """Read file content with proper encoding handling.

        Args:
            file_path: Path to the file

        Returns:
            File content as string

        Raises:
            SystemExit: If the file cannot be read

        """
        try:
            # Try UTF-8 first
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                # Try with error handling
                return file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to read file '{file_path}': {e}"))
                sys.exit(1)

    def _show_dry_run(
        self,
        repository: str,
        title: str,
        body: str,
        base_branch: str,
        head_branch: str,
        files: dict[str, str],
        labels: list[str],
        assignees: list[str],
        reviewers: list[str],
        draft: bool,
    ) -> None:
        """Show what would be done in dry-run mode.

        Args:
            repository: Repository name
            title: PR title
            body: PR body
            base_branch: Base branch
            head_branch: Head branch
            files: Files to upload (local_path -> remote_path)
            labels: Labels to add
            assignees: Assignees to add
            reviewers: Reviewers to add
            draft: Whether to create as draft

        """
        self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
        self.stdout.write(f"Repository: {repository}")
        self.stdout.write(f"Title: {title}")
        self.stdout.write(f"Body: {body}")
        self.stdout.write(f"Base branch: {base_branch}")
        self.stdout.write(f"Head branch: {head_branch}")
        self.stdout.write(f"Draft: {draft}")

        if files:
            self.stdout.write("Files to upload:")
            for local_path, remote_path in files.items():
                # Validate file exists for dry run
                try:
                    file_path = self._validate_file_path(local_path)
                    file_size = file_path.stat().st_size
                    self.stdout.write(f"  {local_path} -> {remote_path} ({file_size} bytes)")
                except SystemExit:
                    self.stdout.write(f"  {local_path} -> {remote_path} (FILE NOT FOUND)")

        if labels:
            self.stdout.write(f"Labels: {', '.join(labels)}")

        if assignees:
            self.stdout.write(f"Assignees: {', '.join(assignees)}")

        if reviewers:
            self.stdout.write(f"Reviewers: {', '.join(reviewers)}")

    def _upload_files(self, repo: Any, head_branch: str, files: dict[str, str]) -> None:
        """Upload files from local filesystem to the repository.

        Args:
            repo: GitHub repository object
            head_branch: Branch to upload files to
            files: Dictionary mapping local file paths to remote file paths

        """
        try:
            # Get the latest commit SHA from base branch
            base_branch = repo.get_branch("main")
            base_sha = base_branch.commit.sha

            # Create the head branch
            try:
                repo.create_git_ref(f"refs/heads/{head_branch}", base_sha)
                logger.info(f"Created branch: {head_branch}")
            except GithubException as e:
                if "Reference already exists" in str(e):
                    logger.info(f"Branch {head_branch} already exists")
                else:
                    raise

            # Upload files
            for local_path, remote_path in files.items():
                try:
                    # Validate and read local file
                    file_path = self._validate_file_path(local_path)
                    content = self._read_file_content(file_path)

                    # Check if file exists in repository
                    try:
                        existing_file = repo.get_contents(remote_path, ref=head_branch)
                        # Update existing file
                        repo.update_file(
                            path=remote_path,
                            message=f"Update {remote_path}",
                            content=content,
                            sha=existing_file.sha,
                            branch=head_branch,
                        )
                        logger.info(f"Updated file: {local_path} -> {remote_path}")
                    except GithubException:
                        # Create new file
                        repo.create_file(
                            path=remote_path,
                            message=f"Create {remote_path}",
                            content=content,
                            branch=head_branch,
                        )
                        logger.info(f"Created file: {local_path} -> {remote_path}")

                except GithubException as e:
                    self.stderr.write(
                        self.style.ERROR(f"Failed to upload {local_path} -> {remote_path}: {e}")
                    )
                    raise
                except SystemExit:
                    # File validation failed, re-raise
                    raise

        except GithubException as e:
            self.stderr.write(self.style.ERROR(f"Failed to upload files: {e}"))
            raise

    def _create_pull_request(
        self,
        repo: Any,
        title: str,
        body: str,
        base_branch: str,
        head_branch: str,
        draft: bool,
    ) -> Any:
        """Create a pull request.

        Args:
            repo: GitHub repository object
            title: PR title
            body: PR body
            base_branch: Base branch
            head_branch: Head branch
            draft: Whether to create as draft

        Returns:
            Created pull request object.

        """
        try:
            pr = repo.create_pull(
                title=title,
                body=body,
                base=base_branch,
                head=head_branch,
                draft=draft,
            )
            logger.info(f"Created Pull Request: {pr.number}")
            return pr

        except GithubException as e:
            self.stderr.write(self.style.ERROR(f"Failed to create Pull Request: {e}"))
            raise

    def _add_labels(self, pr: Any, labels: list[str]) -> None:
        """Add labels to the pull request.

        Args:
            pr: Pull request object
            labels: List of label names

        """
        try:
            pr.add_to_labels(*labels)
            logger.info(f"Added labels: {', '.join(labels)}")
        except GithubException as e:
            self.stderr.write(self.style.WARNING(f"Failed to add labels: {e}"))

    def _add_assignees(self, pr: Any, assignees: list[str]) -> None:
        """Add assignees to the pull request.

        Args:
            pr: Pull request object
            assignees: List of assignee usernames

        """
        try:
            pr.add_to_assignees(*assignees)
            logger.info(f"Added assignees: {', '.join(assignees)}")
        except GithubException as e:
            self.stderr.write(self.style.WARNING(f"Failed to add assignees: {e}"))

    def _add_reviewers(self, pr: Any, reviewers: list[str]) -> None:
        """Add reviewers to the pull request.

        Args:
            pr: Pull request object
            reviewers: List of reviewer usernames

        """
        try:
            pr.add_to_reviewers(*reviewers)
            logger.info(f"Added reviewers: {', '.join(reviewers)}")
        except GithubException as e:
            self.stderr.write(self.style.WARNING(f"Failed to add reviewers: {e}"))
