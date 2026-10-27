"""Private, append-only report evidence with conservative pregame eligibility."""

import argparse
import hashlib
import io
import json
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd


def utc_now():
    return datetime.now(timezone.utc)


def runtime_provenance():
    """Describe this runtime; historical report exports must not claim this generated them."""
    versions = {}
    for package in ["numpy", "pandas", "scikit-learn", "scipy"]:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return {
        "recorded_at": timestamp(utc_now()).isoformat(),
        "code_sha256": {
            p.relative_to(Path(__file__).parents[1]).as_posix(): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in Path(__file__).parents[1].rglob("*.py")
        },
        "versions": versions,
    }


def timestamp(value):
    result = pd.Timestamp(value)
    if pd.isna(result) or result.tzinfo is None:
        raise ValueError("Evidence timestamps must include a timezone")
    return result.tz_convert("UTC")


def eligibility(availability, captured_at):
    """Capture time, not a caller's historical as_of, controls evaluation eligibility."""
    captured = timestamp(captured_at)
    if (
        availability.sleeper_id.isna().any()
        or availability.sleeper_id.duplicated().any()
    ):
        raise ValueError("Evidence requires unique Sleeper player IDs")
    rows = []
    for row in availability.to_dict("records"):
        kickoff = row.get("kickoff")
        known = pd.notna(kickoff) and str(kickoff).strip() != ""
        before = known and timestamp(kickoff) > captured
        rows.append(
            {
                "sleeper_id": str(row["sleeper_id"]),
                "pregame_evidence": bool(before),
                "reason": "captured_before_kickoff"
                if before
                else ("captured_at_or_after_kickoff" if known else "no_known_kickoff"),
            }
        )
    return rows


def _safe_name(name):
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or ":" in name:
        raise ValueError("Unsafe evidence path")
    return str(path)


def capture(report_dir, archive_dir):
    """Seal inputs and forecasts locally. Does not send, upload, or backdate anything."""
    root = Path(report_dir).resolve()
    payloads = {}

    def read(relative):
        relative = _safe_name(relative)
        source = root / relative
        if not source.resolve().is_relative_to(root):
            raise ValueError("Evidence input escapes report directory")
        content = source.read_bytes()
        payloads[relative] = content
        return content

    def document(relative):
        return json.loads(read(relative).decode("utf-8-sig"))

    # Explicit allowlist: never archive environment files, SMTP settings or report mail.
    plan = document("plan/plan-report.json")
    if plan["status"] != "offensive_lineup_created":
        raise ValueError("Only completed plans can be captured")
    season, week = int(plan["season"]), int(plan["week"])
    if not 1 <= week <= 18 or int(plan["history_cutoff"]) >= season * 100 + week:
        raise ValueError("Evidence plan has invalid week or training cutoff")
    context = document("context/manifest.json")
    observed = []
    for name in ["games.csv", "players.json"]:
        content = read("context/" + name)
        if hashlib.sha256(content).hexdigest() != context[name]["sha256"]:
            raise ValueError("Context checksum mismatch")
        observed.append(timestamp(context[name]["fetched_at"]))
    pointer = document("data/current.json")
    snapshot = "data/" + _safe_name(pointer["snapshot"])
    data_manifest = document(snapshot + "/manifest.json")
    for name, digest in data_manifest["files"].items():
        if (
            hashlib.sha256(read(snapshot + "/" + _safe_name(name))).hexdigest()
            != digest
        ):
            raise ValueError("Data snapshot checksum mismatch")
    observed.extend(
        timestamp(s["fetched_at"]) for s in data_manifest["sources"].values()
    )
    league = document("league/import-report.json")
    observed.append(timestamp(league["fetched_at"]))
    for name in [
        "league-supported-offense.json",
        "offensive-slots.json",
        "slots.json",
        "rosters.csv",
        "my_roster.csv",
    ]:
        read("league/" + name)
    for name in ["availability.csv", "projections.csv", "lineup.csv"]:
        read("plan/" + name)
    for name in [
        "specialists.csv",
        "forecast-provenance.json",
        "waivers.csv",
        "waiver-add-drop.csv",
        "waiver-coverage.csv",
        "waiver-availability.csv",
        "waiver-report.json",
        "shadow-projections.csv",
        "shadow-history.csv",
        "shadow-report.json",
    ]:
        if (root / "plan" / name).exists():
            read("plan/" + name)
    availability = pd.read_csv(
        io.BytesIO(payloads["plan/availability.csv"]), dtype={"sleeper_id": str}
    )
    if "plan/shadow-report.json" in payloads:
        shadow = json.loads(payloads["plan/shadow-report.json"])
        if shadow["status"] == "recorded":
            if int(shadow["history_cutoff"]) >= season * 100 + week:
                raise ValueError("Shadow training cutoff is not pregame")
            for name, key in [
                ("shadow-history.csv", "history_sha256"),
                ("projections.csv", "baseline_sha256"),
            ]:
                if hashlib.sha256(payloads["plan/" + name]).hexdigest() != shadow[key]:
                    raise ValueError("Shadow evidence checksum mismatch")
            observed.append(timestamp(shadow["generated_at"]))
            observed.extend(
                timestamp(source["fetched_at"]) for source in shadow["sources"]
            )
    captured = timestamp(utc_now())
    if max(observed + [timestamp(plan["as_of"])]) > captured:
        raise ValueError("Source or plan timestamp is in the future")
    manifest = {
        "schema_version": 1,
        "captured_at": captured.isoformat(),
        "plan_as_of": plan["as_of"],
        "latest_source_observed_at": max(observed).isoformat(),
        "season": season,
        "week": week,
        "files": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in payloads.items()
        },
        "capture_runtime": runtime_provenance(),
        "forecast_provenance_recorded": "plan/forecast-provenance.json" in payloads,
        "eligibility": eligibility(availability, captured),
        "privacy": "Private league inputs. Keep outside public Git and public Actions artifacts.",
        "limitations": [
            "Capture proves what was saved by this tool, not that provider values were historically published at plan_as_of.",
            "Hashes detect accidental changes; this is not a signed or independently timestamped record.",
            "Pregame eligibility is not playing status. Missing box scores must not be converted to DNP or zero.",
            "Snapshots are local unless a separate private persistence service is configured.",
        ],
    }
    directory = Path(archive_dir) / str(season) / f"week-{week:02d}"
    directory.mkdir(parents=True, exist_ok=True)
    filename = captured.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex + ".zip"
    target = directory / filename
    # Exclusive creation avoids silently replacing earlier predictions on reruns.
    with (
        target.open("xb") as stream,
        ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive,
    ):
        for name, content in payloads.items():
            archive.writestr(name, content)
        archive.writestr(
            "evidence-manifest.json", json.dumps(manifest, indent=2).encode("utf-8")
        )
    verify(target)
    return target


def verify(path):
    """Check archive integrity without extracting paths or executing saved content."""
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate evidence members")
        for name in names:
            _safe_name(name)
        manifest = json.loads(archive.read("evidence-manifest.json"))
        if manifest["schema_version"] != 1 or set(names) != set(manifest["files"]) | {
            "evidence-manifest.json"
        }:
            raise ValueError("Unexpected evidence members or version")
        for name, digest in manifest["files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("Evidence checksum mismatch")
        available = pd.read_csv(
            io.BytesIO(archive.read("plan/availability.csv")), dtype={"sleeper_id": str}
        )
        if eligibility(available, manifest["captured_at"]) != manifest["eligibility"]:
            raise ValueError("Evidence eligibility mismatch")
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("capture")
    create.add_argument("--report", type=Path, required=True)
    create.add_argument("--archive", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("path", type=Path)
    args = parser.parse_args()
    path = (
        capture(args.report, args.archive) if args.command == "capture" else args.path
    )
    manifest = verify(path)
    print(
        json.dumps(
            {
                "path": str(path),
                "captured_at": manifest["captured_at"],
                "pregame_players": sum(
                    row["pregame_evidence"] for row in manifest["eligibility"]
                ),
                "total_players": len(manifest["eligibility"]),
            }
        )
    )


if __name__ == "__main__":
    main()
