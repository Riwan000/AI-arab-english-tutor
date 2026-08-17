-- In-progress (unfinished) conversations, so a user who closes the tab
-- mid free-talk can resume where they left off. One draft per user
-- (upsert on user_id) — no support for multiple concurrent drafts.
create table draft_conversations (
    id bigint generated always as identity primary key,
    user_id bigint not null references users(id) on delete cascade,
    lesson_id text,
    mode text not null default 'free_talk',
    difficulty text,
    messages jsonb not null default '[]'::jsonb,
    updated_at timestamptz not null,
    unique (user_id)
);

create index idx_draft_conversations_user_id on draft_conversations (user_id);
