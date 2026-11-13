"""Conservative nflverse play candidates, not validated Sleeper scoring.

Primary field definitions: https://nflreadr.nflverse.com/articles/dictionary_pbp.html
Sleeper lists categories but does not specify edge-case attribution:
https://support.sleeper.com/en/articles/3998131-what-scoring-options-are-available
https://support.sleeper.com/en/articles/3278982-special-teams-scoring-options

Only pass/run fourth-down failures and single-fumble pass/run/punt/kickoff
plays are supported. Penalty plays remain unresolved (a penalty indicator does
not establish whether the event survives enforcement). Multi-fumble sequence,
tries, and other play types are deliberately not reconstructed from prose.
"""

import numpy as np
import pandas as pd

KEYS = ["season", "week", "team", "game_id"]
EVENT_COMPONENTS = (
    "def_4_and_stop",
    "fum_rec",
    "ff",
    "def_st_fum_rec",
    "def_st_ff",
    "def_td",
)
SOURCES = [
    "https://nflreadr.nflverse.com/articles/dictionary_pbp.html",
    "https://support.sleeper.com/en/articles/3998131-what-scoring-options-are-available",
    "https://support.sleeper.com/en/articles/3278982-special-teams-scoring-options",
]


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _number(value):
    try:
        value = float(value)
        return value if np.isfinite(value) else None
    except (ValueError, TypeError):
        return None


class DefenseEventAudit:
    """Return report, team-game candidates, and positive/unresolved event evidence.

    ``complete_game_ids`` is a caller attestation of complete play coverage,
    not merely completed-game status. Without it source_count is always unknown;
    observed_source_count still records the reproducible supported subset.
    """

    def audit(self, raw, *, season, through_week, complete_game_ids=()):
        if (
            isinstance(season, bool)
            or not isinstance(season, int)
            or season < 1
            or isinstance(through_week, bool)
            or not isinstance(through_week, int)
            or not 1 <= through_week <= 18
        ):
            raise ValueError("Expected integer season and regular-season through-week")
        required = {
            "season",
            "week",
            "season_type",
            "game_id",
            "play_id",
            "home_team",
            "away_team",
        }
        if not required.issubset(raw.columns):
            raise ValueError(
                "Missing play identity fields: "
                + ", ".join(sorted(required - set(raw.columns)))
            )
        data = raw.copy()
        for key in ("season", "week", "play_id"):
            data[key] = pd.to_numeric(data[key], errors="raise")
            if not np.isfinite(data[key]).all() or data[key].mod(1).ne(0).any():
                raise ValueError("Play identity numbers must be finite integers")
        data = data.loc[
            data.season.eq(season)
            & data.week.between(1, through_week)
            & data.season_type.eq("REG")
        ]
        if data.empty:
            raise ValueError("No regular-season plays in the requested window")
        for key in ("game_id", "home_team", "away_team"):
            if data[key].map(_text).isna().any():
                raise ValueError("Game and team identities cannot be blank")
        if data.duplicated(["game_id", "play_id"]).any():
            raise ValueError("Duplicate game/play identity")
        if data.home_team.eq(data.away_team).any():
            raise ValueError("Home and away teams must differ")
        if (
            data.groupby("game_id")[["season", "week", "home_team", "away_team"]]
            .nunique()
            .gt(1)
            .any()
            .any()
        ):
            raise ValueError("Conflicting game metadata")
        complete = set(complete_game_ids)
        if complete - set(data.game_id):
            raise ValueError("Coverage attestation includes unknown game IDs")
        evidence = []
        for row in data.sort_values(["game_id", "play_id"]).to_dict("records"):
            teams = (row["home_team"], row["away_team"])
            base = {key: row[key] for key in ("season", "week", "game_id", "play_id")}

            def emit(key, team=None, reason="", count=None, *, teams=teams, base=base):
                for target in (team,) if team in teams else teams:
                    evidence.append(
                        {
                            **base,
                            "team": target,
                            "scoring_key": key,
                            "source_count": count,
                            "status": "candidate_event" if count else "unresolved",
                            "reason": reason,
                        }
                    )

            play = _text(row.get("play_type"))
            if play == "no_play" or _number(row.get("no_play")) == 1:
                continue
            # Administrative rows are not plays. Unknown play types are retained.
            if play in ("timeout", "quarter_end", "game_end"):
                continue
            penalty = _number(row.get("penalty"))
            down = _number(row.get("down"))
            defense = _text(row.get("defteam"))
            offense = _text(row.get("posteam"))
            failed = _number(row.get("fourth_down_failed"))
            if (
                down == 4
                or failed == 1
                or (down is None and play not in ("punt", "kickoff", "extra_point"))
            ):
                if play in ("punt", "field_goal") and failed == 0:
                    pass
                elif penalty != 0:
                    emit("def_4_and_stop", defense, "Penalty or missing penalty flag")
                elif play not in ("pass", "run"):
                    emit("def_4_and_stop", defense, "Unsupported fourth-down play type")
                elif down != 4 or failed not in (0, 1):
                    emit(
                        "def_4_and_stop",
                        defense,
                        "Missing or inconsistent fourth-down fields",
                    )
                elif failed == 1:
                    if (
                        _number(row.get("fourth_down_converted")) != 0
                        or defense not in teams
                        or offense not in teams
                        or defense == offense
                    ):
                        emit(
                            "def_4_and_stop",
                            defense,
                            "Conflicting outcome or missing possession attribution",
                        )
                    else:
                        emit(
                            "def_4_and_stop", defense, "Explicit fourth-down failure", 1
                        )
            touchdown = _number(row.get("touchdown"))
            scoring_team = _text(row.get("td_team"))
            if touchdown not in (0, 1):
                emit("def_td", reason="Missing touchdown indicator")
            elif touchdown == 1 and play not in ("punt", "kickoff"):
                if play not in ("pass", "run") or penalty != 0:
                    emit("def_td", reason="Unsupported touchdown play or penalty")
                elif offense not in teams or defense not in teams or offense == defense:
                    emit("def_td", reason="Missing touchdown possession attribution")
                elif scoring_team == offense:
                    pass  # Offensive recovery touchdowns do not belong to D/ST.
                elif (
                    scoring_team != defense or _number(row.get("return_touchdown")) != 1
                ):
                    emit("def_td", reason="Unresolved touchdown team or return flag")
                elif _number(row.get("interception")) == 1:
                    emit(
                        "def_td",
                        defense,
                        "Explicit defensive interception-return touchdown",
                        1,
                    )
                elif (
                    _number(row.get("fumble")) == 1
                    and _text(row.get("fumble_recovery_1_team")) == defense
                    and "fumble_recovery_2_team" in row
                    and _text(row.get("fumble_recovery_2_team")) is None
                ):
                    emit(
                        "def_td",
                        defense,
                        "Explicit defensive fumble-return touchdown",
                        1,
                    )
                else:
                    emit(
                        "def_td",
                        reason="Unresolved defensive touchdown turnover sequence",
                    )
            fumble = _number(row.get("fumble"))
            if fumble == 0:
                continue
            if play in ("punt", "kickoff"):
                recover_key, force_key = "def_st_fum_rec", "def_st_ff"
            elif play in ("pass", "run"):
                recover_key, force_key = "fum_rec", "ff"
            else:
                for key in ("fum_rec", "ff", "def_st_fum_rec", "def_st_ff"):
                    emit(key, reason="Unknown fumble or unsupported play type")
                continue
            if fumble != 1 or penalty != 0:
                for key in (recover_key, force_key):
                    emit(key, reason="Unknown fumble indicator or penalty disposition")
                continue
            fumbler = _text(row.get("fumbled_1_team"))
            # Explicit second-slot columns are required: missing schema is not
            # evidence that no second event occurred.
            single = all(
                key in row
                for key in (
                    "fumbled_2_team",
                    "fumble_recovery_2_team",
                    "forced_fumble_player_2_team",
                )
            ) and not any(
                _text(row.get(key))
                for key in (
                    "fumbled_2_team",
                    "fumble_recovery_2_team",
                    "forced_fumble_player_2_team",
                )
            )
            if (
                not single
                or fumbler not in teams
                or (
                    play in ("pass", "run")
                    and (
                        fumbler != offense or defense not in teams or defense == offense
                    )
                )
            ):
                for key in (recover_key, force_key):
                    emit(key, reason="Complex fumble sequence or missing attribution")
                continue
            recovery = _text(row.get("fumble_recovery_1_team"))
            if recovery in teams:
                if recovery != fumbler:
                    emit(recover_key, recovery, "Single opponent fumble recovery", 1)
            elif _number(row.get("fumble_out_of_bounds")) != 1:
                emit(recover_key, reason="Recovery team absent")
            forced = _number(row.get("fumble_forced"))
            forcing_team = _text(row.get("forced_fumble_player_1_team"))
            if forced == 1 and forcing_team in teams and forcing_team != fumbler:
                emit(
                    force_key,
                    forcing_team,
                    "Explicit single forced-fumble attribution",
                    1,
                )
            elif forced != 0 or forcing_team is not None:
                emit(force_key, reason="Forced-fumble flag or attribution unresolved")
        events = pd.DataFrame(
            evidence,
            columns=KEYS
            + ["play_id", "scoring_key", "source_count", "status", "reason"],
        )
        candidates = []
        for game in (
            data.drop_duplicates("game_id").sort_values("game_id").to_dict("records")
        ):
            for team in sorted((game["home_team"], game["away_team"])):
                for key in EVENT_COMPONENTS:
                    selected = events.loc[
                        events.game_id.eq(game["game_id"])
                        & events.team.eq(team)
                        & events.scoring_key.eq(key)
                    ]
                    observed = int(selected.status.eq("candidate_event").sum())
                    unresolved = int(selected.status.eq("unresolved").sum())
                    known = game["game_id"] in complete and unresolved == 0
                    candidates.append(
                        {
                            **{k: game[k] for k in ("season", "week", "game_id")},
                            "team": team,
                            "scoring_key": key,
                            "source_count": observed if known else np.nan,
                            "observed_source_count": observed,
                            "unresolved_plays": unresolved,
                            "status": "candidate_mapping"
                            if known
                            else "incomplete_or_unresolved",
                        }
                    )
        report = {
            "schema_version": 1,
            "season": season,
            "through_week": through_week,
            "plays": len(data),
            "games": int(data.game_id.nunique()),
            "complete_game_ids": sorted(complete),
            "ready_for_scoring": False,
            "sources": SOURCES,
            "components": list(EVENT_COMPONENTS),
            "limitations": "Candidate source events only; Sleeper edge rules and historical settings remain unverified. Penalty plays and complex fumbles unresolved. Complete-game coverage must be explicitly attested; missing data is never a full-game zero.",
        }
        return report, pd.DataFrame(candidates), events
