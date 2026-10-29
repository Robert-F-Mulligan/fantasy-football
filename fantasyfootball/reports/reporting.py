"""Email report rendering and durable, fail-closed delivery coordination."""

import base64
import json
import smtplib
import ssl
from email.message import EmailMessage
from hashlib import sha256
from html import escape
from math import isfinite
from pathlib import Path

import pandas as pd
import requests

from fantasyfootball.reports.lineup import render_lineup_brief


def render_ranges(board, selected, metadata):
    """Email-safe range plot using table cells, with numeric fallbacks and a shared axis."""
    needed = {"prediction_lower", "prediction_upper", "projected_points"}
    if not needed.issubset(board):
        return "<p>Prediction ranges unavailable for this report.</p>"
    plotted = board.dropna(subset=list(needed)).copy()
    plotted = plotted.loc[
        plotted[list(needed)].apply(lambda column: column.map(isfinite)).all(axis=1)
        & plotted.prediction_lower.le(plotted.projected_points)
        & plotted.projected_points.le(plotted.prediction_upper)
    ]
    if plotted.empty:
        return "<p>Prediction ranges unavailable: insufficient historical evidence.</p>"
    lower = min(0.0, float(plotted.prediction_lower.min()))
    upper = max(float(plotted.prediction_upper.max()), lower + 1)
    span = upper - lower
    width = 260
    rows = []
    inner_target = metadata.get("inner_target_coverage", 0.5)
    target = metadata.get("target_coverage", 0.8)
    has_inner = False
    for row in plotted.sort_values(
        ["pos", "projected_points"], ascending=[True, False]
    ).to_dict("records"):
        lo, point, hi = (
            row["prediction_lower"],
            row["projected_points"],
            row["prediction_upper"],
        )
        left = max(0, round((lo - lower) / span * width))
        before = max(0, round((point - lo) / span * width))
        after = max(0, round((hi - point) / span * width))
        color = "#166c80" if row["player_id"] in selected else "#667085"
        inner_lo = row.get("prediction_inner_lower", float("nan"))
        inner_hi = row.get("prediction_inner_upper", float("nan"))
        valid_inner = (
            pd.notna(inner_lo)
            and pd.notna(inner_hi)
            and isfinite(inner_lo)
            and isfinite(inner_hi)
            and lo <= inner_lo <= point <= inner_hi <= hi
        )
        has_inner |= valid_inner
        if valid_inner:
            inner_left = max(0, round((inner_lo - lo) / span * width))
            inner_before = max(0, before - inner_left)
            inner_after = max(0, round((inner_hi - point) / span * width))
            segments = [
                (left, "#ffffff", 8),
                (inner_left, "#b6dce2", 8),
                (inner_before, "#68a9b5", 18),
                (4, color, 24),
                (inner_after, "#68a9b5", 18),
                (max(0, after - inner_after), "#b6dce2", 8),
            ]
        else:
            segments = [
                (left, "#ffffff", 8),
                (before, "#b6dce2", 8),
                (4, color, 24),
                (after, "#b6dce2", 8),
            ]
        cells = "".join(
            f'<td width="{n}" valign="middle" style="width:{n}px;padding:0"><div style="background-color:{c};height:{height}px;line-height:{height}px;font-size:1px">&nbsp;</div></td>'
            for n, c, height in segments
            if n
        )
        inner_label = (
            f"{inner_target:.0%}: {inner_lo:.1f} to {inner_hi:.1f}<br>"
            if valid_inner
            else "Inner range unavailable<br>"
        )
        label = escape(str(row["player_name"]))
        decision = "START" if row["player_id"] in selected else "SIT"
        rows.append(
            f'<tr><td style="padding:8px">{label}<br><small>{decision} / {escape(str(row["pos"]))}</small></td><td><table role="presentation" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table></td><td style="padding:8px;white-space:nowrap">{inner_label}{target:.0%}: {lo:.1f} to {hi:.1f}<br><b>{point:.1f} projected</b></td></tr>'
        )
    checks = []
    for position, info in metadata.get("positions", {}).items():
        coverage = info.get("observed_coverage")
        if coverage is not None:
            check = f"{escape(position)}: {coverage:.0%} of {info['validation_rows']} later observations inside the {target:.0%} range"
            inner_coverage = info.get("observed_inner_coverage")
            if inner_coverage is not None:
                check += f"; {inner_coverage:.0%} inside the {inner_target:.0%} range"
            checks.append(check)
    range_title = f"{inner_target:.0%} / {target:.0%}" if has_inner else f"{target:.0%}"
    legend = (
        "Thick darker bar: inner prediction range. Thin pale bar: outer prediction range."
        if has_inner
        else "Thin pale bar: outer prediction range."
    )
    return (
        f'<h2>Projected points and {range_title} target ranges</h2><p>Dark marker: point estimate. {legend} Shared scale: {lower:.0f} to {upper:.0f} points. START/SIT labels remain readable without color.</p><table cellpadding="0" cellspacing="0">'
        + "".join(rows)
        + "</table><p>"
        + ("; ".join(checks) or "Independent coverage check unavailable.")
        + "</p><p>Ranges use past out-of-sample errors for each position. They are not confidence intervals, floor/ceiling guarantees, or an 80% chance of beating another player. DNP/injury risk is not included. Players without bars lack enough evidence or are outside the modeled scope. Overlap is not a statistical significance test. Both ranges are estimated separately from historical errors; injury status is shown separately.</p>"
    )


def render_specialists(plan_dir, metadata):
    path = plan_dir / "specialists.csv"
    if not path.exists():
        return "", "", set()
    frame = pd.read_csv(path, dtype={"sleeper_id": str})
    rows, lines = [], []
    for row in frame.to_dict("records"):
        points = row["projected_points"]
        values = [
            row["player_name"],
            row["pos"],
            row.get("starter_slot"),
            row.get("opp"),
            row.get("kickoff"),
            row["availability"],
            row["recommendation"],
            f"{points:.1f}" if pd.notna(points) else "Unavailable",
            row.get("warning"),
            row["model_note"],
        ]
        values = [str(v) if pd.notna(v) else "" for v in values]
        safe = [escape(v) for v in values]
        rows.append(
            '<div style="border:1px solid #d6dee5;padding:12px;margin-bottom:12px">'
            + f"<b>{safe[0]} ({safe[1]})</b><p>Current slot: {safe[2] or 'Bench'} | Opponent: {safe[3] or 'Unavailable'}<br>"
            + f"Kickoff (UTC): {safe[4] or 'Unavailable'}<br>Availability: {safe[5]}</p>"
            + f"<p><b>{safe[6]}</b> | Kicking estimate: {safe[7]}</p>"
            + f"<p>{safe[8]} {safe[9]}</p></div>"
        )
        lines.append(" | ".join(values))
    limitation = metadata.get("limitations", "")
    blocker = metadata.get("kicker_blocker", "")
    html = (
        "<h2>Kicker and defense</h2><p>Kicker numbers are a separate kicking-only research baseline. Current slots reflect Sleeper; defense has no start/sit recommendation.</p>"
        + "".join(rows)
        + "<p>"
        + escape(limitation + " " + blocker)
        + "</p>"
    )
    return (
        html,
        "\n\nKicker and defense (kickoffs UTC):\n"
        + "\n".join(lines)
        + "\n"
        + limitation
        + " "
        + blocker,
        set(frame.sleeper_id),
    )


def render_report(plan_dir, team_name, season, week):
    plan_dir = Path(plan_dir)
    audit = json.loads((plan_dir / "plan-report.json").read_text(encoding="utf-8"))
    availability = pd.read_csv(plan_dir / "availability.csv", dtype={"player_id": str})
    projections = pd.read_csv(plan_dir / "projections.csv", dtype={"player_id": str})
    if audit["status"] != "offensive_lineup_created":
        raise ValueError(
            "Cannot email a lineup recommendation: "
            + audit.get("reason", "plan blocked")
        )
    lineup = pd.read_csv(plan_dir / "lineup.csv", dtype={"player_id": str})
    board = availability.merge(
        projections[
            ["player_id", "projected_points"]
            + [
                c
                for c in [
                    "prediction_lower",
                    "prediction_upper",
                    "prediction_inner_lower",
                    "prediction_inner_upper",
                    "range_status",
                    "history_games",
                ]
                if c in projections
            ]
        ],
        on="player_id",
        how="left",
        validate="one_to_one",
    )
    specialist_html, specialist_text, specialist_ids = render_specialists(
        plan_dir, audit.get("specialists", {})
    )
    board = board.loc[~board.sleeper_id.astype(str).isin(specialist_ids)].copy()
    selected = set(lineup.player_id)
    brief_html, brief_text = render_lineup_brief(board, lineup)
    range_visual = render_ranges(board, selected, audit.get("prediction_ranges", {}))
    title = f"{team_name} \u2014 Week {week} Start/Sit Report ({season})"
    omissions = ", ".join(audit["unsupported_scoring"]) or "none"
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(title)}</title></head><body style="font-family:Arial,sans-serif;color:#182538">
<h1>{escape(title)}</h1>
<p>Data as of {escape(audit["as_of"])}. Training cutoff: {audit["history_cutoff"]}.</p>
{brief_html}
<p>Check injury and active status before kickoff. Locked players show preweek estimates, not remaining points.</p>
{range_visual}
{specialist_html}
<p>The main lineup and ranges cover offense. Kicker estimates, when available, are separate kicking-only baselines; team defense points are not modeled. Unsupported offensive scoring: {escape(omissions)}. Rookies and players with little history may have weak forecasts. No lineup changes were submitted.</p>
<p>Sources: <a href="https://sleeper.com">Sleeper</a>, <a href="https://github.com/nflverse/nflverse-data">nflverse player data</a>, <a href="https://github.com/nflverse/nfldata">NFL schedule</a>.</p></body></html>"""
    plain = title + "\n\n" + brief_text
    plain += (
        f"\n\nData as of {audit['as_of']}. Training cutoff: {audit['history_cutoff']}."
    )
    plain += f"\n\nOffensive research only. Defense points not modeled; kicker baselines are separate. Unsupported scoring: {omissions}. Recheck injuries before kickoff. No lineup changes submitted."
    if "prediction_lower" in board:
        target = audit.get("prediction_ranges", {}).get("target_coverage", 0.8)
        inner_target = audit.get("prediction_ranges", {}).get(
            "inner_target_coverage", 0.5
        )
        plain += f"\n\nHistorical prediction ranges ({target:.0%} outer target, not guaranteed; excludes DNP/injury risk):"
        for row in board.dropna(
            subset=["prediction_lower", "prediction_upper"]
        ).itertuples():
            plain += f"\n{row.player_name}: {target:.0%}: {row.prediction_lower:.1f} to {row.prediction_upper:.1f}"
            inner_lo = getattr(row, "prediction_inner_lower", float("nan"))
            inner_hi = getattr(row, "prediction_inner_upper", float("nan"))
            if pd.notna(inner_lo) and pd.notna(inner_hi):
                plain += f"; {inner_target:.0%}: {inner_lo:.1f} to {inner_hi:.1f}"
    plain += "\nLocked players show preweek estimates, not remaining points."
    plain += specialist_text
    return title, plain, html


class GmailSMTP:
    def __init__(self, username, password):
        if not username or not password:
            raise ValueError("Gmail sender and app password are required")
        self.username = username
        self.password = password

    def send(self, recipient, subject, plain, html, message_id):
        message = EmailMessage()
        message["From"] = self.username
        message["To"] = recipient
        message["Subject"] = subject
        message["Message-ID"] = message_id
        message.set_content(plain, charset="utf-8")
        message.add_alternative(html, subtype="html", charset="utf-8")
        with smtplib.SMTP_SSL(
            "smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=60
        ) as smtp:
            smtp.login(self.username, self.password)
            refused = smtp.send_message(message)
            if refused:
                raise RuntimeError("SMTP rejected a recipient")


class GitHubDeliveryLedger:
    """Persist reservation before SMTP. Ambiguous failures require manual resolution."""

    BRANCH = "report-delivery-state"

    def __init__(self, repository, token, session=None):
        if not repository or not token:
            raise ValueError("GitHub repository and token are required")
        self.base = f"https://api.github.com/repos/{repository}"
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        )

    def request(self, method, path, **kwargs):
        response = self.session.request(method, self.base + path, timeout=30, **kwargs)
        return response

    def ensure_branch(self):
        response = self.request("GET", f"/git/ref/heads/{self.BRANCH}")
        if response.status_code == 200:
            return
        if response.status_code != 404:
            response.raise_for_status()
        repo = self.request("GET", "")
        repo.raise_for_status()
        base = self.request("GET", "/git/ref/heads/" + repo.json()["default_branch"])
        base.raise_for_status()
        created = self.request(
            "POST",
            "/git/refs",
            json={
                "ref": "refs/heads/" + self.BRANCH,
                "sha": base.json()["object"]["sha"],
            },
        )
        created.raise_for_status()

    def get(self, key):
        response = self.request(
            "GET", f"/contents/delivery/{key}.json", params={"ref": self.BRANCH}
        )
        if response.status_code == 404:
            return None, None
        response.raise_for_status()
        data = response.json()
        return json.loads(base64.b64decode(data["content"])), data["sha"]

    def put(self, key, record, sha=None):
        body = {
            "message": "Record weekly report delivery state",
            "branch": self.BRANCH,
            "content": base64.b64encode(
                json.dumps(record, sort_keys=True).encode()
            ).decode(),
        }
        if sha:
            body["sha"] = sha
        response = self.request("PUT", f"/contents/delivery/{key}.json", json=body)
        response.raise_for_status()
        return response.json()["content"]["sha"]


def deliver_once(
    ledger,
    mailer,
    recipient,
    league_id,
    season,
    week,
    subject,
    plain,
    html,
    *,
    report_type="lineup",
):
    if report_type not in {"lineup", "waivers"}:
        raise ValueError("Unknown report type")
    identity = f"{recipient.lower()}:{league_id}:{season}:{week}"
    # Preserve the original lineup key, so existing deliveries stay deduplicated.
    if report_type == "waivers":
        identity += ":waivers"
    key = sha256(identity.encode()).hexdigest()
    ledger.ensure_branch()
    existing, _ = ledger.get(key)
    if existing:
        if existing.get("status") == "sent":
            return "already_sent"
        raise RuntimeError(
            "Delivery is pending/uncertain; inspect Gmail Sent before resolving the ledger"
        )
    message_id = f"<fantasy-{key}@weekly-report.local>"
    # Reserve durably first. A lost SMTP response must never cause automatic duplicate mail.
    sha = ledger.put(key, {"status": "pending", "message_id": message_id})
    mailer.send(recipient, subject, plain, html, message_id)
    ledger.put(key, {"status": "sent", "message_id": message_id}, sha=sha)
    return "sent"
