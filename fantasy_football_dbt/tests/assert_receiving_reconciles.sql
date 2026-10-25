with raw as (
    select count(*) as targets from {{ ref('int_receiving') }}
), mart as (
    select coalesce(sum(targets), 0) as targets from {{ ref('fct_receiving_weekly') }}
)
select raw.targets from raw cross join mart where raw.targets <> mart.targets
