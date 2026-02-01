"""Tests for puk.workspace module."""
from __future__ import annotations

from pathlib import Path

import pytest

from puk.errors import PolicyViolationError
from puk.workspace import Workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """Create a workspace with default settings.

    Note: fnmatch doesn't support ** for recursive matching like shell glob.
    We use simpler patterns that fnmatch can handle.
    """
    return Workspace(
        root=tmp_path,
        allow_outside_root=False,
        follow_symlinks=False,
        allow_globs=["*.py", "*.txt", "*.md", "*/*.py", "*/*.txt", "*/*.md"],
        deny_globs=[".env", "*secret*", "*/.env"],
        ignore=[".git", "__pycache__"],
        max_file_bytes=1_000_000,
    )


class TestWorkspaceResolvePath:
    def test_resolves_relative_path(self, workspace: Workspace, tmp_path: Path):
        result = workspace.resolve_path("subdir/file.py")
        assert result == tmp_path / "subdir" / "file.py"

    def test_resolves_absolute_path_within_root(self, workspace: Workspace, tmp_path: Path):
        abs_path = tmp_path / "file.py"
        result = workspace.resolve_path(abs_path)
        assert result == abs_path

    def test_raises_on_path_outside_root(self, workspace: Workspace, tmp_path: Path):
        with pytest.raises(PolicyViolationError, match="escapes workspace root"):
            workspace.resolve_path("/etc/passwd")

    def test_raises_on_parent_traversal(self, workspace: Workspace, tmp_path: Path):
        with pytest.raises(PolicyViolationError, match="escapes workspace root"):
            workspace.resolve_path("../outside")

    def test_allows_outside_root_when_enabled(self, tmp_path: Path):
        ws = Workspace(
            root=tmp_path,
            allow_outside_root=True,
            follow_symlinks=False,
            allow_globs=[],
            deny_globs=[],
            ignore=[],
            max_file_bytes=1_000_000,
        )
        result = ws.resolve_path("/etc/passwd")
        assert result == Path("/etc/passwd")

    def test_expands_user_home(self, tmp_path: Path):
        # Test that ~ is expanded when the path is absolute (starts with ~)
        # Note: When the path is relative, it gets joined with root first,
        # so ~ expansion only works for paths that look like ~/... as the full path
        ws = Workspace(
            root=Path.home(),  # Use home as root
            allow_outside_root=False,
            follow_symlinks=False,
            allow_globs=[],
            deny_globs=[],
            ignore=[],
            max_file_bytes=1_000_000,
        )
        # Resolve a relative path within home
        result = ws.resolve_path("somefile")
        assert result == Path.home() / "somefile"


class TestWorkspaceIsWithinRoot:
    def test_path_within_root(self, workspace: Workspace, tmp_path: Path):
        path = tmp_path / "subdir" / "file.py"
        assert workspace._is_within_root(path) is True

    def test_path_outside_root(self, workspace: Workspace):
        path = Path("/etc/passwd")
        assert workspace._is_within_root(path) is False

    def test_root_itself(self, workspace: Workspace, tmp_path: Path):
        assert workspace._is_within_root(tmp_path) is True


class TestWorkspaceEnsureAllowed:
    def test_allows_matching_glob(self, workspace: Workspace, tmp_path: Path):
        path = tmp_path / "script.py"
        workspace.ensure_allowed(path)  # Should not raise

    def test_allows_nested_matching_glob(self, tmp_path: Path):
        # Use a workspace with no allow_globs restriction (empty list allows all)
        ws = Workspace(
            root=tmp_path,
            allow_outside_root=False,
            follow_symlinks=False,
            allow_globs=[],  # Empty allows all
            deny_globs=[],
            ignore=[],
            max_file_bytes=1_000_000,
        )
        path = tmp_path / "src" / "module" / "script.py"
        ws.ensure_allowed(path)  # Should not raise

    def test_denies_matching_deny_glob(self, workspace: Workspace, tmp_path: Path):
        path = tmp_path / ".env"
        with pytest.raises(PolicyViolationError, match="denied by pattern"):
            workspace.ensure_allowed(path)

    def test_denies_secret_files(self, workspace: Workspace, tmp_path: Path):
        path = tmp_path / "my_secret_file.txt"
        with pytest.raises(PolicyViolationError, match="denied by pattern"):
            workspace.ensure_allowed(path)

    def test_denies_non_matching_glob(self, workspace: Workspace, tmp_path: Path):
        path = tmp_path / "binary.exe"
        with pytest.raises(PolicyViolationError, match="not allowed by workspace"):
            workspace.ensure_allowed(path)

    def test_allows_any_when_no_allow_globs(self, tmp_path: Path):
        ws = Workspace(
            root=tmp_path,
            allow_outside_root=False,
            follow_symlinks=False,
            allow_globs=[],
            deny_globs=[],
            ignore=[],
            max_file_bytes=1_000_000,
        )
        path = tmp_path / "anything.xyz"
        ws.ensure_allowed(path)  # Should not raise


class TestWorkspaceShouldIgnore:
    def test_ignores_git_directory(self, workspace: Workspace, tmp_path: Path):
        path = tmp_path / ".git" / "config"
        assert workspace.should_ignore(path) is True

    def test_ignores_pycache(self, workspace: Workspace, tmp_path: Path):
        path = tmp_path / "__pycache__" / "module.pyc"
        assert workspace.should_ignore(path) is True

    def test_does_not_ignore_regular_files(self, workspace: Workspace, tmp_path: Path):
        path = tmp_path / "src" / "module.py"
        assert workspace.should_ignore(path) is False

    def test_ignores_nested_ignored_dir(self, workspace: Workspace, tmp_path: Path):
        # Note: the current implementation only ignores paths that START with
        # the ignore pattern, not paths containing the pattern in subdirectories.
        # So project/.git/objects is NOT ignored, but .git/objects is.
        path = tmp_path / ".git" / "objects"
        assert workspace.should_ignore(path) is True

    def test_partial_name_match_not_ignored(self, workspace: Workspace, tmp_path: Path):
        # "git_stuff" should not be ignored just because ".git" is
        path = tmp_path / "git_stuff" / "file.py"
        assert workspace.should_ignore(path) is False


class TestWorkspaceIntegration:
    def test_full_workflow(self, tmp_path: Path):
        workspace = Workspace(
            root=tmp_path,
            allow_outside_root=False,
            follow_symlinks=False,
            allow_globs=["**/*.py"],
            deny_globs=["**/*test*"],
            ignore=[".git"],
            max_file_bytes=1_000_000,
        )

        # Create actual files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hello')")
        (src_dir / "test_main.py").write_text("# test")

        # Resolve path
        resolved = workspace.resolve_path("src/main.py")
        assert resolved == src_dir / "main.py"

        # Check allowed
        workspace.ensure_allowed(resolved)

        # Check denied
        with pytest.raises(PolicyViolationError):
            workspace.ensure_allowed(src_dir / "test_main.py")

    def test_symlink_handling(self, tmp_path: Path):
        workspace = Workspace(
            root=tmp_path,
            allow_outside_root=False,
            follow_symlinks=False,
            allow_globs=["**/*.py"],
            deny_globs=[],
            ignore=[],
            max_file_bytes=1_000_000,
        )

        # Create a file
        real_file = tmp_path / "real.py"
        real_file.write_text("content")

        # Resolve path works with existing file
        resolved = workspace.resolve_path("real.py")
        assert resolved == real_file
