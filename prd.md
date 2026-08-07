# Product Requirements Document (PRD)
# AI English Tutor for Arabic Speakers
## Phase 1 - Guided AI Conversation MVP

**Version:** 1.0  
**Status:** Draft  
**Owner:** Product Team  
**Target Platform:** Streamlit Web Application

---

# 1. Overview

## Product Vision

Build an AI-powered English tutor that teaches one grammar concept at a time and immediately reinforces it through guided conversation.

Unlike ChatGPT or Duolingo, the AI understands exactly what lesson the student has learned and limits the conversation to that knowledge level while providing instant corrections and explanations in Arabic.

This MVP is intended to validate that lesson-aware AI conversations improve English learning for Arabic-speaking beginners.

---

# 2. Problem Statement

Most language learning applications suffer from one or more of the following problems:

- Lessons are disconnected from practice.
- Chatbots quickly become too difficult.
- Grammar mistakes are corrected without explanation.
- Explanations are only available in English.
- Learners don't know why something is wrong.

The goal of this product is to bridge the gap between learning grammar and actually using it.

---

# 3. Goals

### Primary Goal

Help Arabic learners practice English immediately after learning a grammar concept.

### Success Criteria

- Student completes a conversation of at least 10 exchanges.
- AI detects grammar mistakes accurately.
- AI explains mistakes in both English and Arabic.
- AI continues the conversation naturally.
- Student never feels "stuck."

---

# 4. Target Audience

## Primary Users

- Arabic native speakers
- Beginner English learners (A1)
- Early Intermediate learners (A2)

Examples

- Students
- Professionals
- Travelers
- Anyone preparing for English interviews

---

# 5. Scope

## Included

- Lesson selection
- Grammar lesson viewer
- AI chat interface
- Grammar correction
- Arabic explanations
- Conversation scoring
- Session summary

## Excluded

- Voice conversation
- Pronunciation analysis
- Speech recognition
- User authentication
- Payments
- Course management
- Adaptive curriculum

---

# 6. User Flow

```
Open App

↓

Choose Lesson

↓

Read Mini Lesson

↓

Start Conversation

↓

AI asks first question

↓

Student replies

↓

AI analyzes response

↓

Grammar Correction

↓

Arabic Explanation

↓

Continue Conversation

↓

End Session

↓

Performance Summary
```

---

# 7. Functional Requirements

## Module 1 — Lesson Selection

### Description

The learner selects the grammar topic to practice.

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

## Module 2 — Lesson Viewer

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

## Module 3 — Conversation Engine

### Description

The AI acts as an English tutor.

The conversation should feel natural.

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
- Stay inside the lesson.
- Encourage speaking.
- Never suddenly switch topics.
- Never become too advanced.

---

### Acceptance Criteria

- Conversation history maintained.
- AI remembers previous replies.
- AI limits grammar complexity.

---

# Module 4 — Grammar Analysis

Every user response is analyzed.

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

# Module 5 — Correction Panel

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

# Module 6 — Arabic Explanation

Every correction includes Arabic.

Example

English

```
Present Simple uses the base verb.
```

Arabic

```
في زمن المضارع البسيط نستخدم الفعل بصيغته الأساسية.
```

Requirements

- Modern Standard Arabic
- Beginner friendly
- No complex grammar terminology

---

# Module 7 — Continue Conversation

After correction

Conversation must continue naturally.

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

---

# Module 8 — Progress Summary

When user clicks End Session

Display

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

## Recommendation

```
Practice Present Simple again tomorrow.
```

---

# 8. AI Prompt Design

Prompt templates are stored as **YAML files** in `prompts/` (not embedded in Python):

- `system_prompt.yaml` — base tutor behavior and JSON correction format
- `lesson_context.yaml` — lesson rules, vocabulary, student level, native language
- `start_conversation.yaml` — opening message when a session begins

`prompt_loader.py` reads the YAML; `prompt_builder.py` fills placeholders and appends conversation history.

## System Prompt Inputs

Every conversation receives

```
Lesson Name

Grammar Rules

Allowed Grammar

Allowed Vocabulary

Student Level

Native Language

Conversation History
```

---

## Prompt Behavior

The model should

- Act like an English teacher.
- Speak simple English.
- Stay inside the selected lesson.
- Correct mistakes immediately.
- Explain in Arabic.
- Continue naturally.
- Encourage learners.

---

# 9. Data Model

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

## Conversation Message

```json
{
    "role": "assistant",
    "content": "...",
    "timestamp": "...",
    "lesson": "present_simple"
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

# 10. UI Layout

```
------------------------------------------------------------

Sidebar

Lesson
Conversation Score
Mistakes
Vocabulary
End Session

------------------------------------------------------------

Main Window

AI

Student

Correction Card

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

## LLM

- GPT-5.5 / GPT-4.1 / Gemini / Claude

## Storage

- SQLite (optional)
- JSON for lessons

## State Management

- Streamlit Session State

---

# 12. Suggested Project Structure

```
english-ai-tutor/

│

├── app.py

├── prompts/
│   ├── system_prompt.yaml
│   ├── lesson_context.yaml
│   ├── start_conversation.yaml
│   ├── prompt_loader.py
│   └── prompt_builder.py

├── lessons/
│   ├── present_simple.json
│   ├── past_simple.json
│   ├── articles.json

├── components/
│   ├── chat.py
│   ├── lesson_card.py
│   ├── correction_card.py
│   ├── sidebar.py

├── services/
│   ├── openrouter.py
│   ├── grammar.py
│   └── scoring.py

├── models/
│   ├── lesson.py
│   ├── conversation.py

├── data/
│   ├── sessions.db

└── requirements.txt
```

---

# 13. Non-Functional Requirements

### Performance

- AI response under 5 seconds
- Lesson loads under 1 second

### Reliability

- Conversation history never lost during session
- Graceful handling of API failures

### Usability

- Clean, distraction-free interface
- Beginner-friendly design
- Mobile-responsive layout (basic)

---

# 14. Success Metrics

| Metric | Target |
|----------|---------|
| Conversation Completion Rate | >80% |
| Average Conversation Length | >10 turns |
| AI Response Time | <5 seconds |
| Grammar Detection Accuracy | >90% |
| User Satisfaction | >4.5/5 |

---

# 15. Future Enhancements (Out of Scope for Phase 1)

- Voice conversations
- Speech-to-text
- Pronunciation scoring
- Adaptive learning paths
- Spaced repetition
- Vocabulary revision
- Personalized lesson recommendations
- Teacher dashboard
- Student profiles
- Progress history
- Multi-language support
- Gamification and achievements

---

# 16. MVP Definition of Done

Phase 1 is considered complete when a learner can:

1. Open the application.
2. Select an English grammar lesson.
3. Read a short lesson summary.
4. Start a guided AI conversation.
5. Receive immediate grammar corrections.
6. View explanations in both English and Arabic.
7. Continue the conversation naturally without interruption.
8. End the session and receive a summary of grammar performance, vocabulary learned, and common mistakes.

The MVP's primary objective is to validate that **lesson-aware AI conversations with bilingual feedback create a more effective learning experience than a generic AI chatbot**.
