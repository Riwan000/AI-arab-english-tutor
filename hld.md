# High-Level Design (HLD)
# AI English Tutor for Arabic Speakers — Phase 1 MVP

**Version:** 1.1  
**Status:** Revised  
**References:** [prd.md](prd.md) · [tech-stack.md](tech-stack.md) · [directory.md](directory.md)

---

# 1. Purpose

This document consolidates the product requirements, technical architecture, and project structure into a single high-level design. It describes **what** the system does, **how** major parts interact, and **where** responsibilities live — without prescribing low-level implementation detail.

**Core hypothesis to validate:** Lesson-aware AI conversations with bilingual (English + Arabic) feedback outperform a generic chatbot for Arabic-speaking English beginners.

---

# 2. System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Systems                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  OpenRouter  │    │  GPT / Claude │    │   Gemini     │       │
│  │     API      │───►│   / etc.     │    │              │       │
│  └──────┬───────┘    └──────────────┘    └──────────────┘       │
└─────────┼───────────────────────────────────────────────────────┘
          │ HTTPS (chat completions)
          ▼
┌─────────────────────────────────────────────────────────────────┐
│              AI English Tutor (Phase 1 — Streamlit)              │
│                                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  │
│  │   UI     │  │   Prompt     │  │ Services │  │  Lessons   │  │
│  │Components│◄►│   Engine     │◄►│  Layer   │◄►│  (JSON)    │  │
│  └──────────┘  └──────────────┘  └────┬─────┘  └────────────┘  │
│                                       │                          │
│                              ┌────────▼────────┐                 │
│                              │ SQLite (opt.)   │                 │
│                              └─────────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
          ▲
          │ Browser
          │
    ┌─────┴─────┐
    │  Learner  │  Arabic native speaker, A1–A2 English
    └───────────┘
```

**In scope:** Web UI, lesson-aware chat, grammar correction, Arabic explanations, session summary.  
**Out of scope:** Auth, payments, voice, adaptive curriculum, user accounts.

---

# 3. Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Lesson-constrained AI** | The selected grammar lesson bounds vocabulary, tense, and complexity — preventing the chatbot from outrunning the learner. |
| **Learn → Practice → Correct → Continue** | Every exchange follows the PRD loop: mistake detected, explained bilingually, conversation resumes naturally. |
| **Single LLM call** | Conversation, grammar analysis, and Arabic explanation happen in one OpenRouter request — no separate translation service. |
| **Session-first state** | Active learning lives in Streamlit session state for speed and simplicity; SQLite is optional persistence. |
| **Thin layers, clear boundaries** | UI (`components/`), logic (`services/`), data (`models/`, `lessons/`), prompts (`prompts/`) stay separated. |
| **MVP over perfection** | No FastAPI, no auth, no microservices — validate the learning loop first. |

---

# 4. Logical Architecture

The system has four logical layers:

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1 — PRESENTATION (Streamlit)                          │
│  sidebar · lesson_view · chat · correction_card · summary   │
├─────────────────────────────────────────────────────────────┤
│ LAYER 2 — APPLICATION LOGIC                                 │
│  Session orchestration (app.py) · Scoring · Grammar parsing │
├─────────────────────────────────────────────────────────────┤
│ LAYER 3 — AI / PROMPT ENGINE                                │
│  *.yaml prompts · prompt_loader · prompt_builder · openrouter │
├─────────────────────────────────────────────────────────────┤
│ LAYER 4 — DATA                                              │
│  lessons/*.json · session state · SQLite (optional)         │
└─────────────────────────────────────────────────────────────┘
```

### Layer responsibilities

| Layer | Owns | Does not own |
|-------|------|--------------|
| **Presentation** | Rendering, user input, navigation between screens | LLM calls, prompt construction |
| **Application logic** | Session lifecycle, score calculation, feedback aggregation | UI layout, raw HTTP to OpenRouter |
| **AI / Prompt** | System prompt, lesson context injection, API communication | Storing messages long-term |
| **Data** | Lesson content, schemas, optional DB persistence | Business rules |

---

# 5. Application States & Navigation

The app is a **state machine** with three screens, driven by `st.session_state`:

```
                    ┌─────────────────┐
                    │   APP START     │
                    │  lesson = null  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
         ┌──────────│  LESSON VIEW    │◄─────────┐
         │          │ (read + Start)  │          │
         │          └────────┬────────┘          │
         │                   │ Start Practice    │ New Session
         │          ┌────────▼────────┐          │
         │          │   CONVERSATION  │          │
         │          │  (chat loop)    │          │
         │          └────────┬────────┘          │
         │                   │ End Session       │
         │          ┌────────▼────────┐          │
         └─────────►│    SUMMARY      │──────────┘
                    │ (score + recap) │
                    └─────────────────┘
```

### Session state model

```python
{
    "lesson": dict | None,           # Selected lesson JSON
    "messages": list[dict],          # {role, content, feedback?}
    "mistakes": list[GrammarFeedback],
    "vocabulary": list[str],
    "score": dict,
    "conversation_started": bool,
    "session_ended": bool
}
```

The sidebar is **always visible** and reflects live progress (score, mistakes, vocabulary) during conversation.

---

# 6. Core User Journey (End-to-End)

```
1. SELECT     User picks one lesson from sidebar dropdown
      │
2. LEARN      lesson_view shows rules, examples, tips
      │         User clicks "Start Practice"
      ▼
3. CONVERSE   AI sends opening question (auto-triggered)
      │         Loop:
      │           User types English reply
      │           → prompt_builder injects lesson context + history
      │           → openrouter calls LLM
      │           → grammar service extracts JSON corrections
      │           → correction_card renders EN + AR feedback
      │           → AI continues with next question
      ▼
4. SUMMARIZE  User clicks "End Session"
                scoring service computes grammar %, vocab, mistake types
                summary screen shows recommendation
```

**Target:** ≥10 exchanges per session, <5s AI response, learner never feels stuck.

---

# 7. Module Design (PRD → Implementation)

| # | PRD Module | Component(s) | Service(s) | Key behavior |
|---|------------|--------------|------------|--------------|
| 1 | Lesson Selection | `sidebar.py` | — | Load `lessons/*.json`, store in session |
| 2 | Lesson Viewer | `lesson_view.py` | — | Display rules; gate chat behind "Start Practice" |
| 3 | Conversation Engine | `chat.py` | `openrouter.py` | Maintain history; auto-start first AI message |
| 4 | Grammar Analysis | `chat.py` | `grammar.py` | Parse structured JSON from LLM response |
| 5 | Correction Panel | `correction_card.py` | — | Friendly cards; never say "Wrong" |
| 6 | Arabic Explanation | `correction_card.py` | — | MSA, beginner-friendly (generated by LLM) |
| 7 | Continue Conversation | `chat.py` | `prompt_builder.py` | Prompt instructs natural follow-up after correction |
| 8 | Progress Summary | `summary.py` | `scoring.py` | Grammar %, vocab, mistake types, recommendation |

---

# 8. AI Design

## 8.1 Single-call pattern

One OpenRouter request per user message returns:

1. **Conversational reply** (encouraging tutor voice, simple English)
2. **Structured corrections** (JSON block, only when mistakes exist)

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│ Lesson JSON  │────►│ prompt_builder  │────►│ System prompt │
└──────────────┘     │  + history      │     │ + user msg    │
                     └────────┬────────┘     └──────┬───────┘
                              │                     │
                              ▼                     ▼
                     ┌─────────────────────────────────┐
                     │         OpenRouter API          │
                     └────────────────┬────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
           Natural language reply              JSON corrections
           (shown in chat)                    (parsed by grammar.py
                                              → correction_card)
```

## 8.2 Prompt inputs (every request)

Base and lesson templates live in `prompts/*.yaml`; `prompt_builder.py` fills placeholders at runtime.

| Input | Source |
|-------|--------|
| Lesson name & description | `st.session_state.lesson` |
| Grammar rules | `lesson.grammar_rules` |
| Allowed vocabulary | `lesson.allowed_vocabulary` |
| Student level | Fixed: A1–A2 |
| Native language | Fixed: Arabic |
| Conversation history | `st.session_state.messages` |
| Previous mistakes | `st.session_state.mistakes` (future: inject into prompt) |

## 8.3 LLM constraints (enforced via system prompt)

- Stay within selected lesson grammar and vocabulary
- Correct immediately but encouragingly
- Explain in English **and** Modern Standard Arabic
- Continue the conversation — do not pivot to "let's review grammar"
- Output corrections as parseable JSON

## 8.4 Model strategy

OpenRouter abstracts provider choice. Default model via `DEFAULT_MODEL` env var. Swap models without code changes — useful for cost/quality experiments during MVP validation.

---

# 9. Data Design

## 9.1 Lesson (static JSON)

```json
{
  "id": "present_simple",
  "title": "Present Simple",
  "description": "...",
  "examples": [],
  "grammar_rules": [],
  "allowed_vocabulary": [],
  "negative_form": [],
  "question_form": [],
  "tips": []
}
```

**Current lessons:** present_simple, present_continuous, past_simple, articles, prepositions.

> **Gap:** PRD lists "Daily Conversation" — not yet implemented. Add as a sixth lesson or defer to Phase 2.

## 9.2 Runtime models (Pydantic)

| Model | File | Purpose |
|-------|------|---------|
| `Lesson` | `models/lesson.py` | Typed lesson schema |
| `Message` | `models/conversation.py` | Chat message with optional lesson tag |
| `GrammarFeedback` | `models/feedback.py` | Structured correction payload |

## 9.3 Persistence (optional SQLite)

```
conversations ──1:N── messages
      │
      └──1:N── grammar_feedback
```

Written on session end via `services/database.py`. **Not yet wired** in `app.py` — planned hook at summary screen.

---

# 10. UI Layout (Revised)

PRD describes a three-column layout (sidebar + main + right panel). Phase 1 simplifies to **two columns**:

```
┌──────────────────┬────────────────────────────────────────────┐
│     SIDEBAR      │              MAIN AREA                      │
│                  │                                             │
│  Lesson selector │  [Lesson View]  OR  [Chat]  OR  [Summary]  │
│  Grammar score   │                                             │
│  Mistakes list   │  Correction cards inline below AI messages   │
│  Vocabulary      │                                             │
│  End Session     │  Chat input at bottom                       │
│                  │                                             │
└──────────────────┴────────────────────────────────────────────┘
```

The PRD "right panel" (Grammar / Vocabulary / Fluency) is **folded into the sidebar** for MVP simplicity. A dedicated right panel can be added in Phase 2 without architectural changes.

---

# 11. Request Flow (Detailed)

```
User input
    │
    ▼
chat.py ──append──► st.session_state.messages
    │
    ▼
prompt_builder.build_messages(lesson, history)
    │  merges: SYSTEM_PROMPT + lesson rules + vocab + history
    ▼
openrouter.chat_completion(messages)
    │  POST /chat/completions
    ▼
Raw LLM response (text + optional JSON block)
    │
    ├──► Display conversational text in chat bubble
    │
    └──► grammar.extract_feedback(response)
              │
              ├──► Append to st.session_state.mistakes
              └──► correction_card.render(feedback)
    │
    ▼
st.rerun() ──► sidebar reflects updated score/mistakes
```

**On End Session:**

```
summary.py ──► scoring.calculate_session_summary(messages, mistakes)
           ──► (future) database.save_conversation(lesson, messages, score)
```

---

# 12. Scoring Logic (MVP)

| Metric | Calculation (current) | PRD target |
|--------|----------------------|------------|
| Grammar score | `max(0, 100 - mistakes × 10)` | Display as % |
| Exchanges | Count of user messages | ≥10 per session |
| Mistake types | Deduplicated list from feedback | Group by category |
| Vocabulary | Top words from user messages (stop-word filtered) | Words used in session |
| Recommendation | Rule-based on score thresholds | e.g. "Practice again tomorrow" |

Scoring is intentionally simple for MVP. Accuracy of grammar detection depends on LLM quality, not local NLP.

---

# 13. Non-Functional Requirements

| Category | Requirement | Design response |
|----------|-------------|-----------------|
| Performance | AI < 5s, lessons < 1s | JSON lessons loaded from disk; single API call; 30s HTTP timeout |
| Reliability | No lost history during session | All state in `st.session_state`; rerun-safe append pattern |
| Reliability | API failures handled gracefully | `openrouter.py` should catch errors and show friendly message (TODO) |
| Usability | Beginner-friendly, distraction-free | Wide layout, inline corrections, encouraging copy |
| Security | API key protection | `.env` gitignored; `.env.example` for template |
| Scalability | N/A for MVP | Single-user local/session model |

---

# 14. Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENROUTER_API_KEY` | API authentication | — (required) |
| `OPENROUTER_BASE_URL` | API endpoint | `https://openrouter.ai/api/v1` |
| `DEFAULT_MODEL` | LLM model slug | `openai/gpt-4.1` |

---

# 15. Known Gaps (Docs vs Implementation)

| Item | PRD / Tech docs | Current state | Action |
|------|-----------------|---------------|--------|
| Daily Conversation lesson | Listed in PRD | Missing from `lessons/` | Add JSON or defer |
| SQLite persistence | Optional in tech-stack | `database.py` exists, not called | Wire in `summary.py` |
| Previous mistakes in prompt | Listed in tech-stack | Not injected yet | Extend `prompt_builder.py` |
| API error handling | NFR: graceful failures | `raise_for_status()` only | Add try/except + user message |
| Right panel UI | PRD layout | Merged into sidebar | Accept for MVP |
| Vocabulary live tracking | Sidebar shows vocab | `vocabulary` state not populated in chat loop | Wire from user messages |
| Fluency metric | PRD right panel | Not implemented | Defer to Phase 2 |

---

# 16. Future Architecture (Phase 2+)

```
Phase 1 (now)                Phase 2+ (scale)
─────────────                ────────────────
Streamlit monolith    →      React/Next.js frontend
Session state         →      FastAPI backend + JWT auth
SQLite                →      PostgreSQL + pgvector
Single LLM call       →      Langfuse tracing, model routing
No voice              →      Whisper STT + TTS
```

The current layer boundaries (`components/`, `services/`, `prompts/`, `models/`) are designed so business logic can migrate to a FastAPI backend with minimal rewrite — only the presentation layer changes.

---

# 17. Success Metrics (from PRD)

| Metric | Target | How to measure (MVP) |
|--------|--------|------------------------|
| Conversation completion rate | >80% | Sessions reaching summary / total sessions |
| Avg conversation length | >10 turns | `scoring.exchanges` |
| AI response time | <5s | Log timestamps in `openrouter.py` |
| Grammar detection accuracy | >90% | Manual review / eval set (future) |
| User satisfaction | >4.5/5 | Post-session feedback (future) |

---

# 18. Definition of Done (Design ↔ Build)

Phase 1 design is satisfied when:

- [x] Three-screen state machine (lesson → chat → summary)
- [x] Lesson JSON drives AI prompt constraints
- [x] Single OpenRouter call returns chat + structured corrections
- [x] Bilingual correction cards render inline
- [x] Sidebar shows live progress
- [x] Session summary with score, vocab, mistakes, recommendation
- [ ] SQLite save on session end
- [ ] Graceful API error handling
- [ ] Live vocabulary updates in sidebar during chat
- [ ] ≥10-turn conversation tested end-to-end with real API key

---

# 19. Document Map

| Document | Audience | Focus |
|----------|----------|-------|
| **hld.md** (this file) | Engineers, stakeholders | System design, flows, decisions |
| **prd.md** | Product, design | What to build, user stories, acceptance criteria |
| **tech-stack.md** | Engineers | Technology choices, infra, env vars |
| **directory.md** | Engineers | File layout, module mapping |
| **README.md** | New developers | Setup and quick start |

---

*Revised from prd.md v1.0, tech-stack.md v1.0, directory.md, and current scaffold (commit `81ab1d9`).*
