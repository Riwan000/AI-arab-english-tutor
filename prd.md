# Product Requirements Document (PRD)
# AI English Tutor for Arabic Speakers

**Version:** 2.0
**Status:** Draft (Phase 2 — planned, see `docs/VOICE_AGENT_IMPLEMENTATION_PLAN.md`)
**Owner:** Product Team
**Target Platform:** Streamlit Web Application + FastAPI backend

---

# 1. Overview

## Product Vision

Build an AI-powered English tutor that adapts to the difficulty level a learner chooses, and teaches through natural, turn-based **voice** conversation — either inside a structured grammar lesson or in an open-topic **Free Talk** mode — while providing instant corrections and explanations in Arabic across an Arabic-first interface.

Unlike ChatGPT or Duolingo, the AI understands exactly what lesson (or topic) the student is practicing, matches its vocabulary and pacing to the level the learner selected, and lets the learner speak and listen instead of only typing.

## Phase History

### Phase 1 — Guided AI Conversation MVP (Shipped)

Text-only, lesson-constrained Q&A tutor. Single hardcoded difficulty (A1–A2 beginner). No accounts, no usage limits. Corrections were already bilingual; the rest of the UI was English-only.

### Phase 2 — Voice-Based Adaptive Tutor (This Revision)

Builds on the validated Phase 1 MVP by adding:

1. **Voice** — fully cloud, turn-based ("walkie-talkie") voice: record → transcribe → AI replies → speak, via Deepgram (Nova-2 for transcription, Aura for speech).
2. **Difficulty level** — learner selects Beginner / Intermediate / Advanced, independent of lesson topic.
3. **Free Talk mode** — a new open-topic conversation mode alongside the existing lesson-constrained mode; the AI proactively picks a topic when the learner stalls, instead of rigid fixed Q&A.
4. **Arabic-first UI** — extends the existing bilingual corrections to the rest of the learner-facing interface (labels, sidebar, summary, recommendations, limit/error messages).
5. **Accounts & daily usage limits** — new email/password accounts, required so per-user usage can be capped and OpenRouter (LLM) + Deepgram (voice) cost stays bounded.

This MVP revision is intended to validate that **voice-based, difficulty-aware, free-flowing AI conversation** improves English learning for Arabic-speaking learners more than the Phase 1 text-only, single-level experience.

---

# 2. Problem Statement

Most language learning applications suffer from one or more of the following problems:

- Lessons are disconnected from practice.
- Chatbots quickly become too difficult — or stay too easy, since they don't ask the learner their level.
- Grammar mistakes are corrected without explanation.
- Explanations, and the surrounding app, are only available in English.
- Learners don't know why something is wrong.
- Text-only practice does not build listening or speaking skills.
- Conversation stalls the moment the learner runs out of things to say.
- Free, anonymous, unlimited usage has no cost ceiling for the operator.

The goal of this product is to bridge the gap between learning grammar and actually using it — by voice, at the learner's own level, in a language-native interface.

---

# 3. Goals

### Primary Goal

Help Arabic learners practice spoken and written English — immediately after learning a grammar concept, or in free conversation — at a difficulty level they choose themselves.

### Success Criteria

- Student completes a conversation of at least 10 exchanges.
- Student can complete a full voice turn (speak → AI replies → hears it spoken back), not just type.
- Student can select Beginner / Intermediate / Advanced, and the AI's vocabulary and pace visibly match it.
- Student can hold a natural, open-topic conversation in Free Talk mode, not just answer fixed lesson questions.
- AI detects grammar mistakes accurately.
- AI explains mistakes in both English and Arabic, and the mistake can be replayed as Arabic audio.
- AI continues the conversation naturally and proactively picks a new topic if the learner stalls.
- Daily usage is capped without dead-ending the student — a clear Arabic message states the remaining count and when it resets.
- Student never feels "stuck."

---

# 4. Target Audience

## Primary Users

- Arabic native speakers
- Beginner English learners (A1–A2)
- Early Intermediate learners (A2–B1)
- Intermediate to advanced learners (B1–B2+), now explicitly supported via self-selected difficulty

Learners self-select **Beginner**, **Intermediate**, or **Advanced** at the start of each session — the app no longer assumes everyone is a beginner.

Examples

- Students
- Professionals
- Travelers
- Anyone preparing for English interviews

---

# 5. Scope

## Included

- User accounts (email/password sign up & log in)
- Mode selection: Lesson (structured) or Free Talk (open-topic)
- Difficulty selection (Beginner / Intermediate / Advanced)
- Lesson selection (Lesson mode)
- Grammar lesson viewer
- AI chat interface (typed and voice)
- Turn-based voice conversation (speech-to-text, text-to-speech)
- Grammar correction, with spoken Arabic playback
- Arabic-first UI across all learner-facing chrome
- Conversation scoring
- Session summary
- Daily usage limits (text turns and voice calls, capped independently)

## Excluded

- Pronunciation accuracy scoring (voice is transcribed and replied to, but pronunciation itself is not graded)
- Live-streaming / duplex voice (voice stays turn-based, not real-time interruptible)
- Algorithmic adaptive curriculum (difficulty is learner-selected, not auto-adjusted by the AI over time)
- Email verification on signup
- Password reset flow
- Social login (Google/Apple/etc.)
- Payments
- Course management
- Spaced repetition / vocabulary revision system

---

# 6. User Flow

```
Open App

↓

Sign Up / Log In

↓

Choose Mode (Lesson / Free Talk)

↓

Choose Difficulty (Beginner / Intermediate / Advanced)

↓

[Lesson mode] Choose Lesson → Read Mini Lesson
      or
[Free Talk mode] → skip straight to conversation

↓

Start Conversation

↓

AI asks first question (Lesson) or opens a topic (Free Talk)

↓

Student replies — typed, or 🎙️ recorded and transcribed

↓

AI analyzes response

↓

Grammar Correction (with 🔊 Arabic "Listen" button)

↓

AI reply spoken back automatically

↓

Continue Conversation
   (AI proactively picks a new topic if the learner stalls)
   (blocked with an Arabic notice once the daily limit is reached)

↓

End Session

↓

Performance Summary (Arabic-first)
```

---

# 7. Functional Requirements

## Module 1 — Accounts & Authentication

### Description

The learner creates an account or logs in before reaching the tutor, so usage, difficulty, and conversation history are tied to a real identity rather than an anonymous session.

### UI

Email + password Sign Up / Log In form, shown before the mode/difficulty picker. Session persists across a page refresh.

### Acceptance Criteria

- User can sign up with email, password, and display name.
- A duplicate email (case-insensitive) is rejected with a clear error.
- User can log in and remains logged in across a page refresh.
- Invalid credentials show one generic error — the response does not reveal whether the email exists.
- An expired or invalid session returns the user cleanly to the login screen, never a stuck error banner.

---

## Module 2 — Mode & Difficulty Selection

### Description

Immediately after login, the learner chooses how they want to practice — a structured Lesson or open-topic Free Talk — and at what difficulty.

### UI

Two-step picker: Mode (Lesson / Free Talk) → Difficulty (Beginner / Intermediate / Advanced). Lesson mode continues into the existing lesson picker; Free Talk goes straight to conversation start.

### Acceptance Criteria

- User selects exactly one mode and one difficulty before a conversation can begin.
- Difficulty is visibly reflected in the AI's vocabulary, sentence complexity, and correction strictness.
- Mode and difficulty are shown in the sidebar, in Arabic, for the duration of the session.

---

## Module 3 — Lesson Selection

### Description

In Lesson mode, the learner selects the grammar topic to practice.

### UI

Dropdown or cards displaying lessons.

Example

- Present Simple
- Present Continuous
- Past Simple
- Articles
- Prepositions
- Daily Conversation

### Acceptance Criteria

- User can select exactly one lesson.
- Selected lesson is stored in session state.
- Lesson controls the AI prompt.

---

## Module 4 — Lesson Viewer

### Description

Display a short explanation before conversation begins.

### Lesson Contents

- Lesson title
- Grammar explanation
- Examples
- Negative form
- Question form
- Tips

Example

```
Present Simple

We use Present Simple for routines.

Examples

I eat breakfast every morning.

She works in Dubai.

Negative

I don't drink coffee.

Question

Do you work?
```

### Acceptance Criteria

- Lesson loads instantly.
- User must click "Start Practice."

---

## Module 5 — Free Talk Mode

### Description

An open-topic conversation mode with no fixed lesson. The AI picks real-world topics itself and corrects any mistake it hears, not just one grammar point.

### AI Rules

- Keep the conversation flowing like a real back-and-forth: ask follow-ups, react to what the student said.
- If the learner stalls, or says they don't know what to talk about, the AI picks a new topic and starts talking about it rather than waiting.
- Correct any grammar mistake encountered — not scoped to a single lesson's grammar point.

### Acceptance Criteria

- Free Talk sessions never require a lesson to be selected.
- Free Talk sessions save, list, and summarize the same way Lesson sessions do, and display as "Free Talk."

---

## Module 6 — Conversation Engine

### Description

The AI acts as an English tutor. The conversation should feel like a natural back-and-forth, not a rigid Q&A.

Example

```
AI

Hello!

Let's practice Present Simple.

Tell me about your daily routine.
```

Student

```
I eating breakfast every morning.
```

---

### AI Rules

The AI should

- Ask simple questions.
- Match vocabulary, sentence complexity, and correction strictness to the selected difficulty level.
- In Lesson mode: stay inside the lesson, never suddenly switch topics, never become too advanced.
- In Free Talk mode: pick and change topics itself, especially when the learner stalls.
- Encourage speaking.

---

### Acceptance Criteria

- Conversation history maintained.
- AI remembers previous replies.
- AI limits grammar complexity to the selected difficulty.

---

## Module 7 — Grammar Analysis

Every user response is analyzed, whether typed or spoken.

The model should identify

- Grammar mistakes
- Incorrect tense
- Wrong verb form
- Wrong article
- Missing preposition

Example

Input

```
I eating breakfast every morning.
```

Output

```
Mistake

Verb Form

Wrong

I eating

Correct

I eat
```

---

## Module 8 — Correction Panel

Every detected mistake generates a correction card.

Example

```
❌ Your Sentence

I eating breakfast.

-----------------------------------

✅ Better Sentence

I eat breakfast.

-----------------------------------

Grammar Rule

Present Simple uses the base verb.

-----------------------------------

Arabic Explanation

في المضارع البسيط نستخدم الفعل بصيغته الأساسية.

🔊 استمع (Listen)

-----------------------------------

Tip

Try another sentence using "eat".
```

---

### Requirements

Correction should be

- Friendly
- Short
- Encouraging
- Never discouraging
- Playable as Arabic audio via a "🔊 استمع" (Listen) button (see Module 10 — Voice Interaction)

Never say

```
Wrong.
```

Instead

```
Almost!

Great try.

Just one small change.
```

---

## Module 9 — Arabic-First UI

Every correction includes Arabic, and — as of Phase 2 — so does the rest of the learner-facing interface.

Example

English

```
Present Simple uses the base verb.
```

Arabic

```
في زمن المضارع البسيط نستخدم الفعل بصيغته الأساسية.
```

### Scope

- All learner-facing chrome — buttons, sidebar labels, mode/difficulty picker, session summary, recommendations, limit/error messages — is Arabic-first.
- The English-practice content itself (chat messages, lesson examples) stays English; that is the point of the app.
- Arabic text is Modern Standard Arabic, beginner-friendly, with no complex grammar terminology.
- Right-to-left styling is applied only to Arabic-text containers (sidebar, summary, correction card's Arabic block) — not app-wide, so chat bubbles and the mic control stay left-to-right.

---

## Module 10 — Voice Interaction

### Description

Turn-based ("walkie-talkie") voice conversation layered on top of the existing text chat: record → transcribe → send as a normal message → AI replies → reply is spoken back.

### UI

Push-to-talk microphone button in the chat view (the existing text input stays available as an accessibility/fallback path, not removed). AI replies play back automatically as audio. Each correction card's Arabic explanation has a "🔊 استمع" (Listen) button.

### Acceptance Criteria

- Recording produces a transcript that is sent through the same message pipeline as typed input.
- AI text replies are also synthesized to speech and played back automatically.
- The Arabic explanation on any correction card can be replayed on demand.
- Recordings are capped at a reasonable length/file size; oversized uploads are rejected with a clear message rather than failing silently.
- If no Arabic voice is available from the speech provider, the "Listen" button still works via a fallback, rather than failing.

---

## Module 11 — Continue Conversation

After correction, the conversation must continue naturally.

Example

AI

```
Excellent!

Now tell me where you work.
```

Instead of

```
Let's review grammar.
```

If the learner stalls (especially in Free Talk mode), the AI proactively introduces a new topic rather than waiting for the student to speak first.

---

## Module 12 — Daily Usage Limit

### Description

Each account has a daily cap on text turns, and a separate daily cap on voice calls (transcribe + speak), to bound LLM and voice-provider cost per user.

### UI

Sidebar shows "messages remaining today," sourced from the server (not counted client-side, so it can't drift across devices or tabs). When a limit is hit, further use of that feature is disabled for the day and a friendly Arabic message explains the remaining count.

### Acceptance Criteria

- Text messages and voice calls are counted independently — repeatedly tapping the correction card's "Listen" button cannot bypass the text message limit.
- Hitting either limit blocks further use of that feature for the rest of the day, with a clear Arabic message and a remaining count of 0.
- The remaining-count shown in the sidebar always reflects server-side state.

---

## Module 13 — Progress Summary

When user clicks End Session

Display

## Session Info

```
Mode: Free Talk
Difficulty: Intermediate
```

## Grammar Score

```
82%
```

## Vocabulary

```
Breakfast

Usually

Office

Family
```

## Mistakes

```
Verb Form

Articles

Prepositions
```

## Recommendation (Arabic-first)

```
تدرب على المضارع البسيط مرة أخرى غدًا.
(Practice Present Simple again tomorrow.)
```

---

# 8. AI Prompt Design

Prompt templates are stored as **YAML files** in `prompts/` (not embedded in Python):

- `system_prompt.yaml` — base tutor behavior, JSON correction format, and the "keep it flowing / proactively pick a topic if the learner stalls" instruction
- `lesson_context.yaml` — lesson rules, vocabulary, student level, native language (Lesson mode)
- `free_talk_context.yaml` — open-topic conversation instructions: the AI picks real-world topics and corrects any mistake, not just one lesson's grammar point (Free Talk mode)
- `difficulty_levels.yaml` — per level (Beginner / Intermediate / Advanced): vocabulary complexity, pace, and correction-strictness guidance
- `start_conversation.yaml` — opening message when a session begins

`prompt_loader.py` reads the YAML; `prompt_builder.py` fills placeholders, always appends the difficulty block regardless of mode, and appends conversation history.

## System Prompt Inputs

Every conversation receives

```
Lesson Name (Lesson mode only)

Grammar Rules (Lesson mode only)

Allowed Grammar

Allowed Vocabulary

Difficulty Level

Mode (Lesson / Free Talk)

Student Level

Native Language

Conversation History
```

---

## Prompt Behavior

The model should

- Act like an English teacher.
- Speak simple English, matched to the selected difficulty level.
- In Lesson mode: stay inside the selected lesson.
- In Free Talk mode: pick and change topics itself.
- Correct mistakes immediately.
- Explain in Arabic.
- Keep the conversation flowing like a real back-and-forth — ask follow-ups, react to what was said, and pick a new topic if the learner stalls.
- Encourage learners.

---

# 9. Data Model

## User

```json
{
    "id": "uuid",
    "email": "learner@example.com",
    "password_hash": "... (bcrypt, never plain text)",
    "display_name": "...",
    "created_at": "..."
}
```

---

## Lesson

```json
{
    "id": "present_simple",
    "title": "Present Simple",
    "description": "...",
    "examples": [],
    "grammar_rules": [],
    "allowed_vocabulary": []
}
```

---

## Conversation

```json
{
    "id": "uuid",
    "user_id": "uuid",
    "mode": "lesson | free_talk",
    "difficulty": "beginner | intermediate | advanced",
    "lesson_id": "present_simple | null (null when mode is free_talk)",
    "lesson_title": "Present Simple | Free Talk",
    "created_at": "..."
}
```

## Conversation Message

```json
{
    "role": "assistant",
    "content": "...",
    "timestamp": "...",
    "lesson": "present_simple | null"
}
```

---

## Grammar Feedback

```json
{
    "mistake_type": "Verb Form",
    "wrong_text": "I eating",
    "correct_text": "I eat",
    "english_explanation": "...",
    "arabic_explanation": "...",
    "tip": "..."
}
```

---

## Daily Usage

```json
{
    "user_id": "uuid",
    "usage_date": "2026-08-11",
    "message_count": 7,
    "voice_call_count": 3
}
```

---

# 10. UI Layout

```
------------------------------------------------------------

Auth Screen (pre-login)

Email / Password
Sign Up | Log In

------------------------------------------------------------

Mode & Difficulty Picker (post-login, pre-conversation)

Mode: Lesson | Free Talk
Difficulty: Beginner | Intermediate | Advanced

------------------------------------------------------------

Sidebar (in-conversation)

Mode + Difficulty
Lesson (if applicable)
Messages Remaining Today
Conversation Score
Mistakes
Vocabulary
End Session
Log Out

------------------------------------------------------------

Main Window

AI (🔊 spoken reply autoplays)

Student (🎙️ voice or typed)

Correction Card (🔊 استمع)

AI

Student

------------------------------------------------------------

Right Panel

Grammar

Vocabulary

Fluency

------------------------------------------------------------
```

---

# 11. Tech Stack

## Frontend

- Streamlit

## Backend

- Python
- FastAPI (API layer between Streamlit and services)

## LLM

- GPT-5.5 / GPT-4.1 / Gemini / Claude (via OpenRouter)

## Voice

- Deepgram Nova-2 — speech-to-text
- Deepgram Aura — text-to-speech

## Auth

- bcrypt — password hashing
- PyJWT — session tokens

## Storage

- SQLite (users, conversations, messages, grammar feedback, daily usage)
- JSON for lessons

## State Management

- Streamlit Session State

---

# 12. Suggested Project Structure

```
AI-arab-english-tutor/

├── app.py
├── api_client.py

├── api/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── routes/
│   │   ├── chat.py
│   │   ├── lessons.py
│   │   ├── sessions.py
│   │   ├── health.py
│   │   ├── auth.py            (new)
│   │   ├── voice.py           (new)
│   │   └── usage.py           (new)
│   └── schemas/
│       ├── chat.py
│       ├── session.py
│       ├── auth.py            (new)
│       └── voice.py           (new)

├── prompts/
│   ├── system_prompt.yaml
│   ├── lesson_context.yaml
│   ├── free_talk_context.yaml     (new)
│   ├── difficulty_levels.yaml     (new)
│   ├── start_conversation.yaml
│   ├── prompt_loader.py
│   └── prompt_builder.py

├── lessons/
│   ├── present_simple.json
│   ├── present_continuous.json
│   ├── past_simple.json
│   ├── articles.json
│   └── prepositions.json

├── components/
│   ├── chat.py
│   ├── lesson_view.py
│   ├── correction_card.py
│   ├── sidebar.py
│   ├── summary.py
│   ├── auth_view.py           (new)
│   └── mode_picker.py         (new)

├── services/
│   ├── openrouter.py
│   ├── conversation.py
│   ├── grammar.py
│   ├── scoring.py
│   ├── lessons.py
│   ├── database.py
│   ├── errors.py
│   ├── auth.py                (new)
│   ├── voice.py                (new)
│   └── usage.py                (new)

├── repositories/
│   ├── session_repo.py
│   ├── user_repo.py           (new)
│   └── usage_repo.py          (new)

├── models/
│   ├── lesson.py
│   ├── conversation.py
│   ├── feedback.py
│   └── user.py                (new)

├── database/
│   └── english_tutor.db

└── requirements.txt / requirements-api.txt
```

---

# 13. Non-Functional Requirements

### Performance

- AI text response under 5 seconds
- Voice round-trip (record → transcript → reply → spoken audio) under ~8 seconds for a typical turn
- Lesson loads under 1 second

### Reliability

- Conversation history never lost during session
- Graceful handling of API failures (LLM, transcription, and speech-synthesis providers)
- An expired/invalid login session degrades to a clean re-login prompt, never a stuck error state

### Security

- Passwords are hashed (never stored or logged in plain text)
- Login does not reveal whether an email is registered
- Basic rate limiting on signup/login to blunt credential stuffing
- A user can only ever see or list their own conversations

### Cost Control

- Daily per-user limits on text turns and on voice calls (each metered independently) keep combined OpenRouter + Deepgram cost per user bounded and predictable

### Usability

- Clean, distraction-free interface
- Arabic-first for all learner-facing chrome; beginner-friendly design
- Mobile-responsive layout (basic)

---

# 14. Success Metrics

| Metric | Target |
|----------|---------|
| Conversation Completion Rate | >80% |
| Average Conversation Length | >10 turns |
| AI Response Time (text) | <5 seconds |
| Voice Turn Round-Trip Time | <8 seconds |
| Grammar Detection Accuracy | >90% |
| Free Talk Session Share | tracked (validates open-topic mode adoption) |
| Voice Turn Share (of all turns) | tracked (validates voice adoption vs. typed fallback) |
| User Satisfaction | >4.5/5 |

---

# 15. Future Enhancements (Out of Scope for Phase 2)

- Pronunciation accuracy scoring
- Live-streaming / duplex voice (real-time interruption)
- Algorithmic adaptive curriculum (AI-driven level progression, beyond the learner's own selection)
- Spaced repetition
- Vocabulary revision system
- Personalized lesson recommendations
- Teacher dashboard
- Progress history across sessions/dashboards
- Multi-language support (interfaces other than Arabic)
- Gamification and achievements
- Email verification, password reset, and social login

---

# 16. Definition of Done

## Phase 1 (Shipped)

Phase 1 is considered complete when a learner can:

1. Open the application.
2. Select an English grammar lesson.
3. Read a short lesson summary.
4. Start a guided AI conversation.
5. Receive immediate grammar corrections.
6. View explanations in both English and Arabic.
7. Continue the conversation naturally without interruption.
8. End the session and receive a summary of grammar performance, vocabulary learned, and common mistakes.

## Phase 2 (This Revision)

Phase 2 is considered complete when a learner can:

1. Sign up or log in with an email and password.
2. Choose a mode (Lesson or Free Talk) and a difficulty level (Beginner / Intermediate / Advanced).
3. In Lesson mode, select a lesson and read its summary; in Free Talk mode, start a conversation immediately.
4. Hold a conversation by voice — recording a reply, hearing it transcribed and answered, and hearing the AI's reply spoken back — with typing available as a fallback.
5. Receive immediate grammar corrections with an Arabic explanation that can be replayed as audio.
6. Experience a conversation that flows naturally and, in Free Talk mode, that the AI keeps alive by introducing new topics when the learner stalls.
7. Navigate the entire app (outside the English practice content itself) in Arabic.
8. Be stopped gracefully — with a clear Arabic message — once the daily text or voice usage limit is reached, and see it reset the next day.
9. End the session and receive an Arabic-first summary of grammar performance, vocabulary learned, and common mistakes.
10. Trust that only their own conversations are ever visible to them, even while logged in alongside other accounts.

The Phase 2 objective is to validate that **voice-based, difficulty-aware, free-flowing AI conversation with an Arabic-first interface** creates a more effective and more engaging learning experience than the Phase 1 text-only, single-level MVP — within a predictable per-user cost ceiling.
