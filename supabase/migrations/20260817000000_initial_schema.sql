create extension if not exists citext;

create table users (
    id bigint generated always as identity primary key,
    email citext not null unique,
    password_hash text not null,
    display_name text not null,
    created_at timestamptz not null
);

create table auth_attempts (
    id bigint generated always as identity primary key,
    ip text not null,
    email text not null,
    window_date date not null,
    count integer not null default 0,
    unique (ip, email, window_date)
);

create table daily_usage (
    id bigint generated always as identity primary key,
    user_id bigint not null,
    usage_date date not null,
    message_count integer not null default 0,
    voice_call_count integer not null default 0,
    updated_at timestamptz not null,
    unique (user_id, usage_date)
);

create table conversations (
    id bigint generated always as identity primary key,
    user_id bigint references users(id),
    lesson_id text,
    lesson_title text,
    difficulty text,
    mode text default 'lesson',
    created_at timestamptz not null,
    ended_at timestamptz not null,
    grammar_score integer,
    exchange_count integer,
    mistake_count integer,
    vocabulary jsonb,
    recommendation text,
    model_used text
);

create index idx_conversations_ended_at on conversations (ended_at);

create table messages (
    id bigint generated always as identity primary key,
    conversation_id bigint not null references conversations(id) on delete cascade,
    role text not null,
    content text not null,
    timestamp timestamptz not null,
    sequence integer not null,
    lesson_id text,
    has_correction boolean not null default false
);

create index idx_messages_conversation_id on messages (conversation_id);

create table grammar_feedback (
    id bigint generated always as identity primary key,
    conversation_id bigint not null references conversations(id) on delete cascade,
    message_id bigint not null references messages(id) on delete cascade,
    mistake_type text,
    wrong_text text,
    corrected_text text,
    english_explanation text,
    arabic_explanation text,
    tip text
);

create index idx_grammar_feedback_conversation_id on grammar_feedback (conversation_id);
