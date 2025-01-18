with pbp as (
    select * from {{ ref('stg_nflfastr_pbp') }}
)
,
tgts as (
    select
        pbp.play_id,
        pbp.game_id,
        pbp.game_date,
        pbp.season,
        pbp.receiver_id,
        pbp.receiver,
        pbp.posteam

    from pbp

    where
    pbp.play_type = 'pass'
    and pbp.season_type = 'REG'
    and pbp.receiver_id  is not null
),
wr as (
    select 
        pbp.play_id,
        pbp.game_id,
        pbp.air_yards,
        pbp.yards_after_catch,
        pbp.complete_pass,
        pbp.yards_gained,
        pbp.pass_touchdown,
        case 
            when air_yards = yardline_100 then 1 
            else 0
            end as ez_tgts
        , case
            when yardline_100 <= 20 then 1
            else 0
            end as rz_tgts,
        pbp.first_down_pass

    from pbp

    where
    pbp.play_type = 'pass'
    and pbp.season_type = 'REG'
    and pbp.receiver_id  is not null
    and pbp.down is not null -- remove untimed downs
),
combo as (
    select
        tgts.play_id,
        tgts.game_id,
        tgts.game_date,
        tgts.season,
        tgts.receiver_id,
        tgts.receiver,
        tgts.posteam,
        wr.air_yards,
        wr.yards_after_catch,
        wr.complete_pass,
        wr.yards_gained,
        wr.pass_touchdown,
        wr.ez_tgts,
        wr.rz_tgts,
        wr.first_down_pass

    from tgts
    left join wr on wr.play_id = tgts.play_id
                 and wr.game_id = tgts.game_id

)

select * from combo