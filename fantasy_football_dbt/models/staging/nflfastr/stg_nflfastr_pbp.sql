-- Preserve source grain; do not silently deduplicate corrupt ingestion.
select
    md5(game_id::text || ':' || play_id::text) as play_key,
    game_id::text as game_id,
    play_id::integer as play_id,
    season::integer as season,
    week::integer as week,
    season_type::text as season_type,
    game_date::date as game_date,
    posteam::text as posteam,
    defteam::text as defteam,
    play_type::text as play_type,
    receiver_player_id::text as receiver_id,
    receiver_player_name::text as receiver,
    coalesce(air_yards, 0)::double precision as air_yards,
    coalesce(yards_after_catch, 0)::double precision as yards_after_catch,
    coalesce(receiving_yards, 0)::double precision as receiving_yards,
    coalesce(complete_pass, 0)::integer as complete_pass,
    coalesce(pass_touchdown, 0)::integer as pass_touchdown,
    coalesce(first_down_pass, 0)::integer as first_down_pass,
    yardline_100::double precision as yardline_100,
    coalesce(two_point_attempt, 0)::integer as two_point_attempt
from {{ source('fantasyfootball', 'nflfastr_play_by_play') }}
