"""Tests for puk.staging module."""
from __future__ import annotations

from pathlib import Path

import pytest

from puk.errors import ToolExecutionError
from puk.staging import StagedChange, StagingManager


class TestStagedChange:
    def test_write_change(self):
        change = StagedChange(
            kind="write",
            path=Path("/tmp/file.txt"),
            content="hello world",
            reason="test write",
        )
        assert change.kind == "write"
        assert change.path == Path("/tmp/file.txt")
        assert change.content == "hello world"
        assert change.reason == "test write"

    def test_delete_change(self):
        change = StagedChange(kind="delete", path=Path("/tmp/file.txt"))
        assert change.kind == "delete"
        assert change.path == Path("/tmp/file.txt")

    def test_move_change(self):
        change = StagedChange(
            kind="move",
            src=Path("/tmp/old.txt"),
            dst=Path("/tmp/new.txt"),
        )
        assert change.kind == "move"
        assert change.src == Path("/tmp/old.txt")
        assert change.dst == Path("/tmp/new.txt")


class TestStagingManagerBasics:
    def test_initial_state(self):
        manager = StagingManager()
        assert manager.changes == []
        assert manager.has_changes() is False

    def test_stage_write(self):
        manager = StagingManager()
        change = manager.stage_write(Path("/tmp/file.txt"), "content", "reason")
        assert manager.has_changes() is True
        assert len(manager.changes) == 1
        assert change.kind == "write"

    def test_stage_delete(self):
        manager = StagingManager()
        change = manager.stage_delete(Path("/tmp/file.txt"), "deleting")
        assert manager.has_changes() is True
        assert change.kind == "delete"

    def test_stage_move(self):
        manager = StagingManager()
        change = manager.stage_move(
            Path("/tmp/old.txt"), Path("/tmp/new.txt"), "renaming"
        )
        assert manager.has_changes() is True
        assert change.kind == "move"

    def test_multiple_changes(self):
        manager = StagingManager()
        manager.stage_write(Path("/tmp/a.txt"), "a")
        manager.stage_write(Path("/tmp/b.txt"), "b")
        manager.stage_delete(Path("/tmp/c.txt"))
        assert len(manager.changes) == 3

    def test_changes_returns_copy(self):
        manager = StagingManager()
        manager.stage_write(Path("/tmp/file.txt"), "content")
        changes = manager.changes
        changes.clear()  # Modify the returned list
        assert len(manager.changes) == 1  # Original unchanged


class TestStagingManagerRevert:
    def test_revert_all_clears_changes(self):
        manager = StagingManager()
        manager.stage_write(Path("/tmp/a.txt"), "a")
        manager.stage_write(Path("/tmp/b.txt"), "b")
        assert manager.has_changes() is True
        manager.revert_all()
        assert manager.has_changes() is False
        assert manager.changes == []


class TestStagingManagerDiff:
    def test_diff_for_new_file(self, tmp_path: Path):
        manager = StagingManager()
        new_file = tmp_path / "new.txt"
        change = manager.stage_write(new_file, "line1\nline2\n")
        diff = manager.diff_for_change(change)
        assert "+line1" in diff
        assert "+line2" in diff

    def test_diff_for_existing_file(self, tmp_path: Path):
        existing = tmp_path / "existing.txt"
        existing.write_text("old content\n")
        manager = StagingManager()
        change = manager.stage_write(existing, "new content\n")
        diff = manager.diff_for_change(change)
        assert "-old content" in diff
        assert "+new content" in diff

    def test_diff_for_delete(self, tmp_path: Path):
        to_delete = tmp_path / "delete_me.txt"
        to_delete.write_text("goodbye\n")
        manager = StagingManager()
        change = manager.stage_delete(to_delete)
        diff = manager.diff_for_change(change)
        assert "-goodbye" in diff

    def test_diff_for_delete_nonexistent(self, tmp_path: Path):
        nonexistent = tmp_path / "nonexistent.txt"
        manager = StagingManager()
        change = manager.stage_delete(nonexistent)
        diff = manager.diff_for_change(change)
        assert "already deleted" in diff

    def test_diff_for_move(self, tmp_path: Path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        manager = StagingManager()
        change = manager.stage_move(src, dst)
        diff = manager.diff_for_change(change)
        assert "move" in diff
        assert str(src) in diff
        assert str(dst) in diff

    def test_combined_diff(self, tmp_path: Path):
        manager = StagingManager()
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        manager.stage_write(file1, "content1\n")
        manager.stage_write(file2, "content2\n")
        combined = manager.combined_diff()
        assert "content1" in combined
        assert "content2" in combined


class TestStagingManagerApply:
    def test_apply_write_new_file(self, tmp_path: Path):
        manager = StagingManager()
        new_file = tmp_path / "new.txt"
        manager.stage_write(new_file, "hello world")
        applied = manager.apply_all()
        assert len(applied) == 1
        assert new_file.exists()
        assert new_file.read_text() == "hello world"
        assert manager.has_changes() is False

    def test_apply_write_creates_parent_dirs(self, tmp_path: Path):
        manager = StagingManager()
        nested_file = tmp_path / "a" / "b" / "c" / "file.txt"
        manager.stage_write(nested_file, "nested content")
        manager.apply_all()
        assert nested_file.exists()
        assert nested_file.read_text() == "nested content"

    def test_apply_write_overwrites_existing(self, tmp_path: Path):
        existing = tmp_path / "existing.txt"
        existing.write_text("old")
        manager = StagingManager()
        manager.stage_write(existing, "new")
        manager.apply_all()
        assert existing.read_text() == "new"

    def test_apply_delete_file(self, tmp_path: Path):
        to_delete = tmp_path / "delete_me.txt"
        to_delete.write_text("goodbye")
        manager = StagingManager()
        manager.stage_delete(to_delete)
        manager.apply_all()
        assert not to_delete.exists()

    def test_apply_delete_directory(self, tmp_path: Path):
        dir_to_delete = tmp_path / "mydir"
        dir_to_delete.mkdir()
        (dir_to_delete / "file1.txt").write_text("a")
        (dir_to_delete / "file2.txt").write_text("b")
        subdir = dir_to_delete / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("c")

        manager = StagingManager()
        manager.stage_delete(dir_to_delete)
        manager.apply_all()
        assert not dir_to_delete.exists()

    def test_apply_delete_nonexistent_is_noop(self, tmp_path: Path):
        nonexistent = tmp_path / "nonexistent.txt"
        manager = StagingManager()
        manager.stage_delete(nonexistent)
        applied = manager.apply_all()  # Should not raise
        assert len(applied) == 1

    def test_apply_move_file(self, tmp_path: Path):
        src = tmp_path / "source.txt"
        src.write_text("moving content")
        dst = tmp_path / "destination.txt"

        manager = StagingManager()
        manager.stage_move(src, dst)
        manager.apply_all()

        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "moving content"

    def test_apply_move_creates_parent_dirs(self, tmp_path: Path):
        src = tmp_path / "source.txt"
        src.write_text("content")
        dst = tmp_path / "new" / "dir" / "destination.txt"

        manager = StagingManager()
        manager.stage_move(src, dst)
        manager.apply_all()

        assert dst.exists()

    def test_apply_multiple_changes(self, tmp_path: Path):
        manager = StagingManager()

        # Write
        new_file = tmp_path / "new.txt"
        manager.stage_write(new_file, "new content")

        # Delete
        to_delete = tmp_path / "delete.txt"
        to_delete.write_text("delete me")
        manager.stage_delete(to_delete)

        # Move
        src = tmp_path / "src.txt"
        src.write_text("move me")
        dst = tmp_path / "dst.txt"
        manager.stage_move(src, dst)

        applied = manager.apply_all()

        assert len(applied) == 3
        assert new_file.read_text() == "new content"
        assert not to_delete.exists()
        assert dst.read_text() == "move me"
        assert not src.exists()

    def test_apply_with_error_keeps_remaining(self, tmp_path: Path):
        manager = StagingManager()

        # First change will succeed
        good_file = tmp_path / "good.txt"
        manager.stage_write(good_file, "good")

        # Second change will fail (try to move nonexistent file)
        nonexistent = tmp_path / "nonexistent_source.txt"
        dst = tmp_path / "dst.txt"
        manager.stage_move(nonexistent, dst)

        # Apply and expect error
        with pytest.raises(ToolExecutionError):
            manager.apply_all()

        # First change should have been applied
        assert good_file.exists()

        # Failed change should still be in the list
        assert manager.has_changes()
