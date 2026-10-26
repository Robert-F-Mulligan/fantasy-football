"""Persist verified evidence in a private GitHub repository using a scoped deploy key."""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

from .evidence import capture, verify


def require_hidden(repository, session):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Expected a GitHub owner/repository")
    response = session.get(
        f"https://api.github.com/repos/{repository}", timeout=30, allow_redirects=False
    )
    # A dedicated SSH deploy key has no REST metadata permission. Setup verifies
    # private=true with the owner's API session; runtime must remain anonymous-hidden.
    # A 404 alone is NOT evidence of access: the subsequent SSH clone must also work.
    if response.status_code != 404:
        raise ValueError(
            "Archive repository is public, redirected, or privacy check is unavailable"
        )


def normalized_private_key(key):
    """Windows text-mode stdin can introduce CRLF before gh stores a secret."""
    return (
        key.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"
    ).encode("utf-8")


def _git(args, cwd, env):
    result = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, timeout=180, check=False
    )
    if result.returncode:
        # Never forward command output or private paths to public workflow logs.
        error = result.stderr.decode("utf-8", errors="replace").lower()
        reason = "check deploy key and repository access"
        for markers, description in [
            (("error in libcrypto", "invalid format"), "deploy key format is invalid"),
            (("permission denied (publickey)",), "deploy key was not accepted"),
            (("host key verification failed",), "SSH host verification failed"),
            (("repository not found",), "repository is missing or key lacks access"),
            (
                (
                    "connection timed out",
                    "connection refused",
                    "network is unreachable",
                ),
                "SSH connection could not be established",
            ),
        ]:
            if any(marker in error for marker in markers):
                reason = description
                break
        raise RuntimeError("Private archive Git operation failed: " + reason)
    return result.stdout.decode("utf-8").strip()


def publish(archive, repository, key, session=None):
    archive = Path(archive)
    manifest = verify(archive)
    season, week = int(manifest["season"]), int(manifest["week"])
    if not 1900 <= season <= 2200 or not 1 <= week <= 18:
        raise ValueError("Invalid evidence season or week")
    if not key or "PRIVATE KEY" not in key:
        raise ValueError("Missing private archive deploy key")
    if session is None:
        session = requests.Session()
        session.trust_env = (
            False  # No .netrc or ambient REST credentials for visibility check.
        )
    require_hidden(repository, session)
    response = session.get("https://api.github.com/meta", timeout=30)
    response.raise_for_status()
    keys = response.json().get("ssh_keys", [])
    if not keys or not all(
        re.fullmatch(r"(?:ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256) [A-Za-z0-9+/=]+", k)
        for k in keys
    ):
        raise ValueError("GitHub SSH host keys unavailable")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    relative = Path("snapshots") / str(season) / f"week-{week:02d}" / f"{digest}.zip"
    with tempfile.TemporaryDirectory(prefix="ff-evidence-") as directory:
        root = Path(directory)
        identity = root / "identity"
        identity.write_bytes(normalized_private_key(key))
        identity.chmod(0o600)
        hosts = root / "known_hosts"
        hosts.write_text("".join(f"github.com {k}\n" for k in keys), encoding="utf-8")
        env = os.environ.copy()
        env.pop("FF_ARCHIVE_SSH_KEY", None)
        env.update(
            GIT_TERMINAL_PROMPT="0",
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
        )
        env["GIT_SSH_COMMAND"] = " ".join(
            [
                "ssh",
                "-i",
                shlex.quote(identity.as_posix()),
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                "UserKnownHostsFile=" + shlex.quote(hosts.as_posix()),
            ]
        )
        checkout = root / "repository"
        _git(
            [
                "clone",
                "--depth",
                "1",
                "--branch",
                "main",
                f"git@github.com:{repository}.git",
                str(checkout),
            ],
            root,
            env,
        )
        target = checkout / relative
        if not target.resolve().is_relative_to(checkout.resolve()):
            raise ValueError("Archive path escapes repository")
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("Remote archive content does not match its hash")
            return "already_archived"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive, target)
        _git(["add", "--", relative.as_posix()], checkout, env)
        _git(
            [
                "-c",
                "user.name=Fantasy report archive",
                "-c",
                "user.email=archive@users.noreply.github.com",
                "commit",
                "-m",
                "Preserve pregame evidence",
            ],
            checkout,
            env,
        )
        require_hidden(repository, session)
        _git(["push", "origin", "HEAD:main"], checkout, env)
        # Verify the exact remote blob via fetch instead of trusting push exit alone.
        _git(["fetch", "origin", "main"], checkout, env)
        local_blob = _git(["hash-object", str(target)], checkout, env)
        remote_blob = _git(
            ["rev-parse", "FETCH_HEAD:" + relative.as_posix()], checkout, env
        )
        if local_blob != remote_blob:
            raise ValueError("Private archive remote verification failed")
    return "archived_and_verified"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    delivery = json.loads((args.report / "delivery.json").read_text(encoding="utf-8"))
    if delivery["status"] == "offseason":
        status = "offseason"
    else:
        if delivery["status"] != "ready":
            raise ValueError("Only ready reports may be archived")
        archive = capture(args.report, args.report / "private-evidence")
        status = publish(
            archive,
            os.environ["FF_ARCHIVE_REPOSITORY"],
            os.environ["FF_ARCHIVE_SSH_KEY"],
        )
    print("Private evidence:", status)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(f"Private evidence: **{status}**.\n")


if __name__ == "__main__":
    main()
