"""Email report rendering and durable, fail-closed delivery coordination."""

import base64
import json
import smtplib
import ssl
from email.message import EmailMessage
from hashlib import sha256
from html import escape
from pathlib import Path

import pandas as pd
import requests


def render_ranges(board, selected, metadata):
    """Email-safe range plot using table cells, with numeric fallbacks and a shared axis."""
    needed = {"prediction_lower", "prediction_upper", "projected_points"}
    if not needed.issubset(board):
        return "<p>Prediction ranges unavailable for this report.</p>"
    plotted = board.dropna(subset=list(needed)).copy()
    if plotted.empty:
        return "<p>Prediction ranges unavailable: insufficient historical evidence.</p>"
    lower = min(0.0, float(plotted.prediction_lower.min()))
    upper = max(float(plotted.prediction_upper.max()), lower + 1)
    span = upper - lower
    width = 260
    rows = []
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
        segments = [
            (left, "#ffffff"),
            (before, "#b6dce2"),
            (4, color),
            (after, "#b6dce2"),
        ]
        cells = "".join(
            f'<td width="{n}" bgcolor="{c}" style="width:{n}px;height:12px;font-size:1px;line-height:12px">&nbsp;</td>'
            for n, c in segments
            if n
        )
        label = escape(str(row["player_name"]))
        decision = "START" if row["player_id"] in selected else "SIT"
        rows.append(
            f'<tr><td style="padding:8px">{label}<br><small>{decision} / {escape(str(row["pos"]))}</small></td><td><table role="presentation" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table></td><td style="padding:8px;white-space:nowrap">{lo:.1f} to {hi:.1f}<br><b>{point:.1f} projected</b></td></tr>'
        )
    checks = []
    for position, info in metadata.get("positions", {}).items():
        coverage = info.get("observed_coverage")
        if coverage is not None:
            checks.append(
                f"{escape(position)}: {coverage:.0%} of {info['validation_rows']} later observations inside the range"
            )
    target = metadata.get("target_coverage", 0.8)
    return (
        f'<h2>Projected points and {target:.0%} target ranges</h2><p>Dark marker: point estimate. Pale bar: historical error range. Shared scale: {lower:.0f} to {upper:.0f} points. START/SIT labels remain readable without color.</p><table cellpadding="0" cellspacing="0">'
        + "".join(rows)
        + "</table><p>"
        + ("; ".join(checks) or "Independent coverage check unavailable.")
        + "</p><p>Ranges use past out-of-sample errors for each position. They are not confidence intervals, floor/ceiling guarantees, or an 80% chance of beating another player. DNP/injury risk is not included. Players without bars lack enough evidence or are outside the modeled scope. Overlapping ranges indicate that small ranking differences should be treated cautiously.</p>"
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
                for c in ["prediction_lower", "prediction_upper", "range_status"]
                if c in projections
            ]
        ],
        on="player_id",
        how="left",
        validate="one_to_one",
    )
    selected = set(lineup.player_id)
    rows = []
    text_rows = []
    for row in board.to_dict("records"):
        name = row["player_name"] if pd.notna(row["player_name"]) else row["sleeper_id"]
        decision = "START" if row["player_id"] in selected else "SIT"
        if row["availability"] == "unsupported_position":
            decision = "NOT MODELED"
        points = row["projected_points"]
        values = [
            decision,
            name,
            row.get("pos"),
            row.get("opp"),
            f"{points:.1f}" if pd.notna(points) else "\u2014",
            row["availability"],
            row.get("warning"),
        ]
        text_rows.append(" | ".join(str(v) if pd.notna(v) else "?" for v in values))
        rows.append(
            "<tr>"
            + "".join(
                "<td>" + escape(str(v) if pd.notna(v) else "\u2014") + "</td>"
                for v in values
            )
            + "</tr>"
        )
    changes = []
    for row in lineup.to_dict("records"):
        incumbents = board.loc[board.starter_slot.eq(row["slot"])]
        if len(incumbents) == 1 and incumbents.iloc[0].player_id != row["player_id"]:
            old = incumbents.iloc[0]
            # Equivalent slot shuffles among recommended starters are not start/sit changes.
            if old.player_id in selected:
                continue
            gain = row["projected_points"] - old.projected_points
            comparison = (
                f" ({gain:+.1f} projected points)"
                if pd.notna(gain)
                else " (incumbent unavailable or unprojected)"
            )
            changes.append(
                f"{row['slot']}: {row['player_name']} instead of {old.player_name}{comparison}"
            )
    range_visual = render_ranges(board, selected, audit.get("prediction_ranges", {}))
    title = f"{team_name} \u2014 Week {week} Start/Sit Report ({season})"
    summary = (
        "; ".join(changes)
        if changes
        else "No replacement of a current offensive starter is recommended; check slot assignments and availability below."
    )
    omissions = ", ".join(audit["unsupported_scoring"]) or "none"
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(title)}</title></head><body style="font-family:Arial,sans-serif;color:#182538">
<h1>{escape(title)}</h1><p>{escape(summary)}</p>
<p>Data as of {escape(audit["as_of"])}. Training cutoff: {audit["history_cutoff"]}.</p>
{range_visual}
<table border="1" cellpadding="7" cellspacing="0"><tr><th>Decision</th><th>Player</th><th>Pos</th><th>Opponent</th><th>Projected points</th><th>Availability</th><th>Watch</th></tr>{"".join(rows)}</table>
<p>Recommendations maximize projected offensive points subject to eligible slots and kickoff locks. Opponent context comes from historical positional points allowed; this is not a calibrated matchup difficulty grade. Small projected differences are not strong evidence.</p>
<p>Wednesday reports are preliminary. Recheck injuries and active status before kickoff. Started players retain their imported slots; displayed values are preweek estimates, not remaining points.</p>
<p>Kickers and team defense are not modeled. Unsupported offensive scoring: {escape(omissions)}. Rookies and players with little history may have weak forecasts. No lineup changes were submitted.</p>
<p>Sources: <a href="https://sleeper.com">Sleeper</a>, <a href="https://github.com/nflverse/nflverse-data">nflverse player data</a>, <a href="https://github.com/nflverse/nfldata">NFL schedule</a>.</p></body></html>"""
    plain = title + "\n\n" + summary + "\n\n" + "\n".join(text_rows)
    plain += f"\n\nOffensive research only. K/DEF not modeled. Unsupported scoring: {omissions}. Recheck injuries before kickoff. No lineup changes submitted."
    if "prediction_lower" in board:
        plain += "\n\nHistorical prediction ranges (nominal 80%, not guaranteed):"
        for row in board.dropna(
            subset=["prediction_lower", "prediction_upper"]
        ).itertuples():
            plain += f"\n{row.player_name}: {row.prediction_lower:.1f} to {row.prediction_upper:.1f}"
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
    ledger, mailer, recipient, league_id, season, week, subject, plain, html
):
    key = sha256(
        f"{recipient.lower()}:{league_id}:{season}:{week}".encode()
    ).hexdigest()
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
