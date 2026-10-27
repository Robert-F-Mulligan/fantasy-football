"""One-time setup from the owner's authenticated terminal; never prints private keys."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

SOURCE = "Robert-F-Mulligan/fantasy-football"
DESTINATION = "Robert-F-Mulligan/fantasy-football-evidence"


def command(args, *, data=None):
    result = subprocess.run(
        args, input=data, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(
            "Setup command failed: "
            + " ".join(args[:3])
            + ". Check GitHub login and repository administrator access."
        )
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gh", default="gh")
    args = parser.parse_args()
    gh = args.gh
    command([gh, "api", "user"])
    repo = json.loads(command([gh, "api", f"repos/{DESTINATION}"]))
    if repo.get("private") is not True or repo.get("default_branch") != "main":
        raise ValueError("Destination must be private and initialized with main")
    # Don't activate a variable until the deployed workflow understands it.
    workflow = json.loads(
        command(
            [
                gh,
                "api",
                f"repos/{SOURCE}/contents/.github/workflows/weekly-report.yml?ref=main",
            ]
        )
    )
    import base64

    if b"fantasyfootball.archives.private_archive" not in base64.b64decode(workflow["content"]):
        raise ValueError(
            "Merge the reviewed private-archive workflow PR before running setup"
        )
    ssh_keygen = shutil.which("ssh-keygen")
    if not ssh_keygen:
        raise RuntimeError("Install Windows OpenSSH Client to provide ssh-keygen")
    root = Path(__file__).resolve().parents[1] / "work"
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="private-archive-setup-", dir=root
    ) as directory:
        identity = Path(directory) / "identity"
        command(
            [
                ssh_keygen,
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                "fantasy-report-evidence",
                "-f",
                str(identity),
            ]
        )
        payload = json.dumps(
            {
                "title": "Wednesday private evidence archive",
                "key": identity.with_suffix(".pub").read_text().strip(),
                "read_only": False,
            }
        )
        key = json.loads(
            command(
                [
                    gh,
                    "api",
                    "--method",
                    "POST",
                    f"repos/{DESTINATION}/keys",
                    "--input",
                    "-",
                ],
                data=payload,
            )
        )
        try:
            # gh encrypts the secret locally; stdin keeps it out of process arguments.
            command(
                [gh, "secret", "set", "FF_ARCHIVE_SSH_KEY", "--repo", SOURCE],
                data=identity.read_text(),
            )
        except Exception:
            command(
                [
                    gh,
                    "api",
                    "--method",
                    "DELETE",
                    f"repos/{DESTINATION}/keys/{key['id']}",
                ]
            )
            raise
    command(
        [
            gh,
            "variable",
            "set",
            "FF_ARCHIVE_REPOSITORY",
            "--repo",
            SOURCE,
            "--body",
            DESTINATION,
        ]
    )
    command(
        [
            gh,
            "workflow",
            "run",
            "weekly-report.yml",
            "--repo",
            SOURCE,
            "--ref",
            "main",
            "-f",
            "send_email=false",
        ]
    )
    print("Private archive key installed; email-free verification run started.")
    print(f"https://github.com/{SOURCE}/actions/workflows/weekly-report.yml")
    print("No passwords or tokens need to be pasted into chat.")


if __name__ == "__main__":
    main()
