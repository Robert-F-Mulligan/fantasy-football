-- Team-season grain keeps traded-player denominators comparable.
select receiver_id, max(receiver) as receiver, team, season,
    count(*) as games, sum(targets) as targets, sum(catches) as catches,
    sum(air_yards) as air_yards, sum(rec_yards) as rec_yards,
    sum(rec_tds) as rec_tds, sum(rz_tgts) as rz_tgts, sum(ez_tgts) as ez_tgts
from {{ ref('fct_receiving_weekly') }}
group by receiver_id, team, season
