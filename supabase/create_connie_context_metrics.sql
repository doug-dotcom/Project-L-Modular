create table if not exists connie_context_metrics (

    id bigint generated always as identity primary key,

    created_at timestamptz default now(),

    user_message text,

    raw_token_estimate integer,

    compressed_token_estimate integer,

    compression_ratio numeric,

    active_topics text[],

    active_entities text[],

    emotional_tone text,

    continuity_score numeric,

    drift_detected boolean default false,

    packet_summary text,

    final_packet text,

    llm_response_quality text

);

create index if not exists idx_connie_created
on connie_context_metrics(created_at desc);
