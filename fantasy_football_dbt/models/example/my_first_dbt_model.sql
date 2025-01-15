with source_data as (
    select * from {{ source('fantasyfootball', 'nflfastr_play_by_play')}}
),

my_view as (
    select *
    from source_data
    limit 10
)

select * from my_view