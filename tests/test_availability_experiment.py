import numpy as np
import pandas as pd
import pytest

from fantasyfootball.experiments.availability_experiment import (
    FEATURES, build_panel, blocked_interval,
)


def source():
    rows=[]
    for season in [2023,2024]:
        for week in range(1,7):
            for i in range(6):
                if season==2024 and i==0 and week in [3,4,5]:
                    continue
                rows.append(dict(player_id=str(i),player_name=str(i),pos="RB",team="A",
                    season=season,week=week,period=season*100+week,fantasy_points=10+i,
                    rushing_att=10,receiving_tgt=2))
    games=pd.DataFrame([dict(season=s,week=w,game_type="REG",home_team="A",away_team="B",home_score=20)
                       for s in [2023,2024] for w in range(1,7)])
    return pd.DataFrame(rows),games


def test_same_week_and_future_outcomes_cannot_change_predictors():
    history,games=source()
    panel,_=build_panel(history,games)
    changed=history.copy()
    changed.loc[changed.period.ge(202406),["fantasy_points","rushing_att","receiving_tgt"]]=999
    after,_=build_panel(changed,games)
    pd.testing.assert_frame_equal(panel.loc[panel.period.le(202406),FEATURES],after.loc[after.period.le(202406),FEATURES])
    row=panel.loc[panel.period.eq(202406)&panel.player_id.eq("0")].iloc[0]
    assert row.gap==3 and row.last_appearance==0 and row.observed==1
    assert row.points4==10


def test_absences_remain_in_candidate_population_and_byes_do_not():
    history,games=source()
    panel,_=build_panel(history,games)
    row=panel.loc[panel.period.eq(202405)&panel.player_id.eq("0")].iloc[0]
    assert row.observed==0 and row.actual==0
    games=games.loc[~(games.season.eq(2024)&games.week.eq(4))]
    history=history.loc[history.period.ne(202404)]
    panel,_=build_panel(history,games)
    assert not panel.period.eq(202404).any()
    assert panel.loc[panel.period.eq(202406)&panel.player_id.eq("0"),"gap"].iloc[0]==2


def test_missing_team_coverage_is_not_an_absence_label():
    history,games=source()
    history=history.loc[~(history.period.eq(202405)&history.player_id.ne("1"))]
    panel,audit=build_panel(history,games)
    assert not panel.period.eq(202405).any()
    assert audit["excluded_team_coverage_or_transfer_rows"]>0


def test_candidate_set_does_not_include_future_debutants():
    history,games=source()
    late=history.loc[history.player_id.eq("1")&history.period.ge(202405)].copy()
    late["player_id"]="debut"
    panel,_=build_panel(pd.concat([history,late]),games)
    assert not panel.loc[panel.period.le(202405),"player_id"].eq("debut").any()


def test_block_bootstrap_is_paired_and_reproducible():
    frame=pd.DataFrame(dict(period=np.repeat(np.arange(202401,202418),3),baseline=5.,candidate=3.))
    assert blocked_interval(frame,"candidate",resamples=100)==[-2.,-2.]
    assert blocked_interval(frame.iloc[:3],"candidate") is None


def test_outcome_diagnostics_expose_absence_gain_and_return_underprediction():
    from fantasyfootball.experiments.availability_experiment import outcome_diagnostics
    frame=pd.DataFrame([
        dict(period=202500+w,gap=2,observed=observed,actual=actual,baseline=4.,combined=1.)
        for w in range(2,19) for observed,actual in [(0,0.),(1,10.)]
    ])
    result=outcome_diagnostics(frame)
    absent=result["still_absent_after_gap"]
    returned=result["observed_after_gap"]
    assert absent["combined"]["mae"] < absent["baseline"]["mae"]
    assert returned["combined"]["mae"] > returned["baseline"]["mae"]
    assert returned["combined"]["bias"] == -9.
    assert returned["post_outcome_slice"]
    assert result["no_prior_gap"]["baseline"]["mae"] is None
