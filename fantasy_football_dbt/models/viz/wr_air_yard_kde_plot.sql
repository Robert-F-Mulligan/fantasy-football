-- Explicit target-grain distribution input for visualization.
select season, week, receiver_id, receiver, posteam as team, air_yards
from {{ ref('int_receiving') }}
