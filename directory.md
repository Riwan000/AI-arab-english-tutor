# Directory Structure
# AI English Tutor for Arabic Speakers (Phase 1 MVP)

Unified layout reconciling `prd.md` and `tech-stack.md`.

---

## Tree

```
AI-arab-english-tutor/
│
├── app.py                      # Streamlit entry point — wires everything together
├── requirements.txt
├── .env                        # OPENROUTER_API_KEY, DEFAULT_MODEL (not committed)
├── .env.example                # Template for env vars
├── README.md
├── prd.md
├── tech-stack.md
├── directory.md
│
├── components/                 # UI layer (Streamlit widgets)
│   ├── sidebar.py              # Lesson selector, score, mistakes, vocab, End Session
│   ├── lesson_view.py          # Mini lesson viewer before chat starts
│   ├── chat.py                 # Main conversation interface
│   ├── correction_card.py      # Grammar correction cards (EN + AR)
│   └── summary.py              # End-session performance summary
│
├── prompts/
│   ├── system_prompt.py        # Base system prompt template
│   └── prompt_builder.py       # Builds lesson-aware prompts per request
│
├── services/                   # Business logic (no UI)
│   ├── openrouter.py           # OpenRouter API client
│   ├── grammar.py              # Parses LLM response → grammar feedback
│   ├── database.py             # SQLite read/write
│   └── scoring.py              # Grammar score, vocab tracking, recommendations
│
├── models/                     # Data classes / schemas
│   ├── lesson.py               # Lesson model
│   ├── conversation.py         # Message + conversation models
│   └── feedback.py             # GrammarFeedback model
│
├── lessons/                    # Static lesson content (JSON)
│   ├── present_simple.json
│   ├── present_continuous.json
│   ├── past_simple.json
│   ├── articles.json
│   └── prepositions.json
│
├── database/                   # SQLite storage (auto-created at runtime)
│   └── .gitkeep
│
└── assets/                     # Optional: icons, images, CSS
    └── .gitkeep
```

---

## PRD Module Mapping

| Folder / File | PRD Module | Responsibility |
|---|---|---|
| `components/sidebar.py` | Module 1 | Lesson selection, live score, mistakes, vocab |
| `components/lesson_view.py` | Module 2 | Grammar explanation before practice |
| `components/chat.py` | Module 3 | AI conversation engine UI |
| `components/correction_card.py` | Modules 5 & 6 | Correction cards + Arabic explanations |
| `components/summary.py` | Module 8 | Grammar score, vocab, mistakes, recommendations |
| `services/openrouter.py` | Modules 3 & 4 | LLM calls for chat + grammar analysis |
| `services/grammar.py` | Module 4 | Parse mistakes from LLM response |
| `services/scoring.py` | Module 8 | Track score across the session |
| `prompts/prompt_builder.py` | Section 8 | Inject lesson rules, vocab, history into prompt |
| `lessons/*.json` | Section 9 | Lesson data model |
| `models/` | Section 9 | Python types for Lesson, Message, Feedback |
| `database/` | Section 9 | Persist completed sessions (optional for MVP) |

---

## Reconciled Naming Decisions

| Topic | PRD | Tech Stack | **Chosen** |
|---|---|---|---|
| Lesson viewer | `lesson_card.py` | `lesson_view.py` | `lesson_view.py` |
| LLM service | `llm.py` | `openrouter.py` | `openrouter.py` |
| Grammar service | `grammar_parser.py` | `grammar.py` | `grammar.py` |
| Prompt builder location | `services/` | `prompts/` | `prompts/` |
| System prompt | `system_prompt.txt` | `system_prompt.py` | `system_prompt.py` |
| DB folder | `data/sessions.db` | `database/english_tutor.db` | `database/english_tutor.db` |

---

## Request Flow

```
app.py
  │
  ├─► components/sidebar.py        → selects lesson
  ├─► components/lesson_view.py    → shows grammar rules
  ├─► components/chat.py           → user sends message
  │       │
  │       ├─► prompts/prompt_builder.py  → builds system prompt
  │       ├─► services/openrouter.py       → calls LLM
  │       ├─► services/grammar.py          → extracts corrections
  │       └─► components/correction_card.py → displays feedback
  │
  ├─► components/summary.py       → end session
  │       └─► services/scoring.py  → calculates final score
  │
  └─► services/database.py         → saves session to SQLite
```
