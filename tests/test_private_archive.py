from pathlib import Path
from unittest.mock import Mock

import pytest

from fantasyfootball import private_archive


@pytest.mark.parametrize("status", [200, 301, 401, 403, 429, 500])
def test_upload_requires_anonymously_hidden_destination(status):
    session = Mock()
    session.get.return_value.status_code = status
    with pytest.raises(ValueError, match="privacy check"):
        private_archive.require_hidden("owner/private", session)


def test_rejects_invalid_repository_before_network():
    session = Mock()
    with pytest.raises(ValueError, match="owner/repository"):
        private_archive.require_hidden("https://evil.example/repo", session)
    session.get.assert_not_called()


def test_publish_verifies_remote_blob_and_does_not_pass_secret_to_git(
    tmp_path, monkeypatch
):
    archive = tmp_path / "sample.zip"
    archive.write_bytes(b"fixture")
    monkeypatch.setattr(
        private_archive, "verify", lambda p: {"season": 2026, "week": 8}
    )
    session = Mock()

    def get(url, **kwargs):
        response = Mock(status_code=404 if "/repos/" in url else 200)
        response.json.return_value = {"ssh_keys": ["ssh-ed25519 AAAA"]}
        return response

    session.get.side_effect = get
    calls = []

    def git(args, cwd, env):
        assert "FF_ARCHIVE_SSH_KEY" not in env
        assert "StrictHostKeyChecking=yes" in env["GIT_SSH_COMMAND"]
        calls.append(args)
        if args[0] == "clone":
            Path(args[-1]).mkdir()
        return "blob" if args[0] in ["hash-object", "rev-parse"] else ""

    monkeypatch.setattr(private_archive, "_git", git)
    monkeypatch.setenv("FF_ARCHIVE_SSH_KEY", "SECRET PRIVATE KEY")
    assert (
        private_archive.publish(archive, "owner/private", "SECRET PRIVATE KEY", session)
        == "archived_and_verified"
    )
    assert [c[0] for c in calls][-4:] == ["push", "fetch", "hash-object", "rev-parse"]
    assert "SECRET" not in str(calls)


def test_failed_git_does_not_expose_stderr_or_key(monkeypatch, tmp_path):
    monkeypatch.setattr(
        private_archive.subprocess,
        "run",
        lambda *a, **k: Mock(returncode=1, stderr=b"PRIVATE CONTENT"),
    )
    with pytest.raises(RuntimeError, match="deploy key") as exc:
        private_archive._git(["push"], tmp_path, {})
    assert "PRIVATE CONTENT" not in str(exc.value)
