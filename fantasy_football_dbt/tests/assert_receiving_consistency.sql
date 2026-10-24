select player_week_key
from {{ ref('fct_receiving_weekly') }}
where targets < 1 or catches < 0 or catches > targets
   or rec_tds < 0 or rz_tgts > targets or ez_tgts > targets
   or target_share < 0 or target_share > 1 or week not between 1 and 18
