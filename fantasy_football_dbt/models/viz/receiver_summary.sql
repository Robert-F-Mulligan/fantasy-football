with wr as (
    select * from {{ ref('int_receiving') }}
)
,
team_rank as (
    select
        wr.receiver_id,
        wr.posteam,
        ROW_NUMBER() over (partition by wr.receiver_id, wr.season order by wr.game_date) as rn

    from wr
),
last_team as (
    select
        receiver_id,
        posteam
    from team_rank

    where 
        rn = 1
),
team_summary as (
    select
        wr.season,
        wr.posteam,
        COUNT(DISTINCT play_id) as targets,
        SUM(air_yards) as air_yards

    from wr

    group by
        wr.season,
        wr.posteam
),
player_summary as (
    select 
        wr.receiver_id,
        wr.receiver,
        wr.season,
        COUNT(DISTINCT game_id) as games,
        COUNT(play_id) as targets,
        SUM(complete_pass) as catches,
        SUM(air_yards) as air_yards,
        SUM(yards_after_catch) as yards_after_catch,
        AVG(air_yards) as adot, 
        SUM(yards_gained) as rec_yards,
        SUM(pass_touchdown) as rec_tds,
        SUM(rz_tgts) as rz_tgts,
        SUM(ez_tgts) as ez_tgts
    
    from wr

    where
        wr.receiver_id is not null

    group by
        wr.receiver_id,
        wr.receiver,
        wr.season
)

select * from player_summary
