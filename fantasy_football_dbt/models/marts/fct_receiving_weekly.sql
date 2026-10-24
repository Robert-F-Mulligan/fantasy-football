-- Grain: receiver x team x season x week. Traded players retain team context.
with players as (
    select season, week, receiver_id, posteam,
        max(receiver) as receiver,
        count(*)::integer as targets,
        sum(complete_pass)::integer as catches,
        sum(air_yards)::double precision as air_yards,
        sum(yards_gained)::double precision as rec_yards,
        sum(pass_touchdown)::integer as rec_tds,
        sum(rz_tgts)::integer as rz_tgts,
        sum(ez_tgts)::integer as ez_tgts
    from {{ ref('int_receiving') }}
    group by season, week, receiver_id, posteam
), team as (
    select season, week, posteam, sum(targets) as targets, sum(air_yards) as air_yards
    from players group by season, week, posteam
)
select
    md5(p.receiver_id || ':' || p.posteam || ':' || p.season::text || ':' || p.week::text) as player_week_key,
    p.season, p.week, p.receiver_id, p.receiver, p.posteam as team,
    p.targets, p.catches, p.air_yards, p.rec_yards, p.rec_tds, p.rz_tgts, p.ez_tgts,
    (p.targets::double precision / nullif(t.targets, 0))::double precision as target_share,
    (p.air_yards / nullif(t.air_yards, 0))::double precision as air_yard_share
from players p
join team t on p.season=t.season and p.week=t.week and p.posteam=t.posteam
