with pbp as (
    select * from {{ ref('stg_nflfastr_pbp') }}
)
,
wr as (
    select 
        pbp.play_id,
        pbp.game_id,
        pbp.game_date,
        pbp.season,
        pbp.receiver_id,
        pbp.receiver,
        pbp.posteam,
        pbp.air_yards,
        pbp/yards_after_catch,
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
            end as rz_tgts

    from pbp

    where
    pbp.play_type = 'pass'
    and pbp.season_type = 'REG'
    and pbp.receiver_id  is not null
    and pbp.down is not null -- remove untimed downs
)

select * from wr