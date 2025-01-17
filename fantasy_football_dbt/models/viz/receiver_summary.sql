with wr as (
    select * from {{ ref('int_receiving') }}
)
,
team_rank as (
    select
        wr.receiver_id,
        wr.posteam,
        wr.season,
        ROW_NUMBER() over (partition by wr.receiver_id, wr.season order by wr.game_date desc) as rn

    from wr
),
distinct_teams as (
    select distinct
        wr.receiver_id,
        wr.season,
        wr.posteam

    from wr
),
team_count as (
    select distinct
        dt.receiver_id,
        dt.season,
        count(dt.posteam) as team_count

    from distinct_teams dt

    group by
        dt.receiver_id,
        dt.season

),
last_team as (
    select
        receiver_id,
        posteam,
        season

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
        lt.posteam as team,
        tc.team_count,
        wr.season,
        COUNT(DISTINCT game_id) as games,
        COUNT(play_id) as targets,
        SUM(wr.complete_pass) as catches,
        SUM(wr.air_yards) as air_yards,
        SUM(wr.yards_after_catch) as yards_after_catch,
        AVG(wr.air_yards) as adot, 
        SUM(wr.yards_gained) as rec_yards,
        SUM(wr.pass_touchdown) as rec_tds,
        SUM(wr.rz_tgts) as rz_tgts,
        SUM(wr.ez_tgts) as ez_tgts
    
    from wr
    inner join last_team lt on lt.receiver_id = wr.receiver_id
                            and lt.season = wr.season    
    inner join team_count tc on tc.receiver_id = wr.receiver_id
                             and tc.season = wr.season

    where
        wr.receiver_id is not null  

    group by
        wr.receiver_id,
        wr.receiver,
        lt.posteam,
        wr.season,
        tc.team_count
),
combo as (
    select 
        ps.receiver,
        ps.team,
        ps.season,
        ps.games,
        ps.targets,
        ps.catches,
        ps.air_yards,
        case
            when ps.team_count = 1 then ps.air_yards::double precision / ts.air_yards::double precision -- to not skew team stats for players who have moved teams
            else null 
            end as air_yard_share,
        case
            when ps.team_count = 1 then ps.targets::double precision / ts.targets::double precision
            else null 
            end as target_share,
        ps.yards_after_catch,
        ps.adot,
        ps.rec_yards,
        ps.rec_tds,
        ps.rz_tgts,
        ps.ez_tgts

    from player_summary ps
    inner join team_summary ts on ts.season = ps.season
                              and ts.posteam = ps.team
)

select * from combo
