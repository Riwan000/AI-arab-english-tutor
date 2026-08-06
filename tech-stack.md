# Technical Architecture
# AI English Tutor for Arabic Speakers (Phase 1 MVP)

## Version

1.0

---

# 1. Architecture Overview

The Phase 1 MVP follows a lightweight architecture designed for rapid development and validation. The application is built around a Streamlit frontend that communicates with an LLM through the OpenRouter API. All conversation state is managed within the user's session, while completed conversations and analytics can optionally be persisted in a local SQLite database.

```
                    +----------------------+
                    |      User            |
                    +----------+-----------+
                               |
                               |
                        Streamlit Frontend
                               |
                Session State (Current Chat)
                               |
                               |
                    Prompt Builder Service
                               |
                               |
                     OpenRouter API Client
                               |
                +--------------+--------------+
                |                             |
           GPT-5.5                     Claude/Gemini
                |                             |
                +--------------+--------------+
                               |
                        AI Response
                               |
          Grammar Feedback + Arabic Explanation
                               |
                               |
                     Streamlit Interface
                               |
                               |
                  SQLite (Conversation Logs)
```

---

# 2. Technology Stack

| Layer | Technology | Purpose |
|---------|------------|---------|
| Frontend | Streamlit | User interface and chat application |
| Backend (Optional) | FastAPI | Future REST APIs and integrations |
| LLM Provider | OpenRouter | Unified access to multiple LLMs |
| Models | GPT-5.5, GPT-4.1, Claude, Gemini | Conversation, grammar correction, Arabic explanations |
| Prompt Management | Python | Builds lesson-aware prompts |
| Session State | Streamlit Session State | Stores active conversation |
| Database | SQLite | Stores completed conversations and analytics |
| Configuration | Python + Environment Variables | API keys and configuration |

---

# 3. Frontend

## Framework

Streamlit

### Responsibilities

- Lesson selection
- Display lesson content
- Chat interface
- Grammar correction cards
- Session summary
- Progress sidebar

### Components

```
Sidebar

Lesson Selector

Conversation Score

Mistakes

Vocabulary

End Session
```

```
Main Chat

Conversation

Correction Cards

Typing Area
```

```
Summary Screen

Grammar Score

Vocabulary

Recommendations
```

---

# 4. Backend (Optional)

For the MVP, all logic can run directly inside Streamlit.

FastAPI is included as an optional component for future scalability.

Potential future responsibilities include:

- Authentication
- User profiles
- Lesson APIs
- Analytics
- Database APIs
- Mobile application support
- Admin dashboard

During Phase 1, FastAPI is **not required**.

---

# 5. LLM Layer

## Provider

OpenRouter

OpenRouter provides a unified API for multiple language models, allowing the application to switch models without changing business logic.

### Supported Models

- GPT-5.5
- GPT-4.1
- Claude
- Gemini

### Responsibilities

The LLM is responsible for:

- Conducting conversations
- Detecting grammar mistakes
- Correcting sentences
- Explaining grammar in English
- Explaining grammar in Arabic
- Maintaining conversation flow
- Staying within lesson constraints

---

# 6. Prompt Builder

A dedicated Python module constructs the system prompt before every conversation.

The prompt includes:

```
Selected Lesson

Grammar Rules

Allowed Vocabulary

Student Level

Conversation History

Native Language

Previous Mistakes
```

Example Prompt Flow

```
Lesson JSON

↓

Prompt Builder

↓

System Prompt

↓

Conversation History

↓

OpenRouter API
```

---

# 7. Translation

No external translation API is required.

Instead, the selected LLM generates Arabic explanations directly.

Example

```
User

I eating breakfast.
```

LLM returns

```
Correction

I eat breakfast.

English Explanation

Present Simple uses the base verb.

Arabic Explanation

في المضارع البسيط نستخدم الفعل بصيغته الأساسية.
```

Benefits

- No additional API cost
- Better contextual explanations
- One API call instead of multiple services

---

# 8. Session Management

The active conversation is stored using Streamlit Session State.

Example State

```python
st.session_state = {
    "lesson": "...",
    "messages": [],
    "mistakes": [],
    "score": {},
    "conversation_started": True
}
```

Responsibilities

- Store chat history
- Store lesson selection
- Store grammar feedback
- Maintain conversation context
- Prevent data loss during page interactions

---

# 9. Conversation Storage

Database

SQLite

### Stored Information

- Session ID
- Timestamp
- Selected Lesson
- Conversation History
- Grammar Mistakes
- Vocabulary Used
- Final Score

Example Schema

## Conversations

| Column | Type |
|----------|------|
| id | INTEGER |
| lesson | TEXT |
| created_at | DATETIME |
| score | INTEGER |

---

## Messages

| Column | Type |
|----------|------|
| id | INTEGER |
| conversation_id | INTEGER |
| role | TEXT |
| message | TEXT |
| timestamp | DATETIME |

---

## Grammar Feedback

| Column | Type |
|----------|------|
| id | INTEGER |
| conversation_id | INTEGER |
| mistake_type | TEXT |
| wrong_text | TEXT |
| corrected_text | TEXT |
| english_explanation | TEXT |
| arabic_explanation | TEXT |

---

# 10. Project Structure

```
english-ai-tutor/

├── app.py
│
├── components/
│   ├── chat.py
│   ├── sidebar.py
│   ├── lesson_view.py
│   ├── correction_card.py
│   └── summary.py
│
├── prompts/
│   ├── system_prompt.py
│   └── prompt_builder.py
│
├── services/
│   ├── openrouter.py
│   ├── grammar.py
│   ├── database.py
│   └── scoring.py
│
├── lessons/
│   ├── present_simple.json
│   ├── present_continuous.json
│   ├── articles.json
│   └── prepositions.json
│
├── models/
│   ├── lesson.py
│   ├── conversation.py
│   └── feedback.py
│
├── database/
│   └── english_tutor.db
│
├── assets/
│
├── requirements.txt
│
├── .env
│
└── README.md
```

---

# 11. Request Flow

```
User sends message

↓

Streamlit receives input

↓

Conversation stored in Session State

↓

Prompt Builder combines

- Lesson
- Rules
- History
- Student Message

↓

OpenRouter API

↓

Selected LLM

↓

AI Response

↓

Grammar Analysis

↓

Arabic Explanation

↓

Correction Card Generated

↓

Conversation Updated

↓

Displayed to User

↓

(Optional)

Conversation saved to SQLite
```

---

# 12. Environment Variables

```
OPENROUTER_API_KEY=your_api_key

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

DEFAULT_MODEL=openai/gpt-5.5
```

---

# 13. Future Architecture (Beyond MVP)

As the application scales, the architecture can evolve into:

- **Frontend:** React or Next.js
- **Backend:** FastAPI
- **Database:** PostgreSQL
- **Vector Database:** pgvector or Qdrant (for long-term learning history)
- **Authentication:** Clerk or Auth0
- **Caching:** Redis
- **Object Storage:** AWS S3 or Cloudflare R2
- **Deployment:** Docker + Kubernetes
- **Monitoring:** Langfuse, OpenTelemetry
- **Speech Services:** Whisper, Deepgram, or Azure Speech
- **Text-to-Speech:** ElevenLabs or Azure Neural Voices

---

# 14. MVP Architecture Summary

The Phase 1 MVP prioritizes simplicity and rapid iteration. Streamlit provides the entire user interface and application logic, while Streamlit Session State maintains the active conversation. OpenRouter serves as the unified gateway to multiple LLMs, enabling grammar correction, conversational tutoring, and Arabic explanations through a single API. SQLite offers lightweight persistence for conversation logs and learner analytics. This architecture minimizes infrastructure complexity while remaining flexible enough to evolve into a production-grade platform in later phases.
