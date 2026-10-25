-- One regular-season receiving target, excluding two-point conversions.
select
    play_key, play_id, game_id, game_date, season, week,
    receiver_id, receiver, posteam, defteam,
    air_yards, yards_after_catch, complete_pass,
    receiving_yards as yards_gained, pass_touchdown, first_down_pass,
    case when air_yards >= yardline_100 then 1 else 0 end as ez_tgts,
    case when yardline_100 <= 20 then 1 else 0 end as rz_tgts
from {{ ref('stg_nflfastr_pbp') }}
where season_type = 'REG'
  and play_type = 'pass'
  and receiver_id is not null
  and two_point_attempt = 0
