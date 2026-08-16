# Voice Agent — Phase/Task/Subtask Breakdown

Derived from `docs/VOICE_AGENT_IMPLEMENTATION_PLAN.md`. Numbering continues the existing
issue-tracker convention (`[N.M] Title`, labels `phase-N` / `priority-X` / `type-Y`) used for
phases 0–4. Build order follows plan §H: the migration fix (plan §E) is pulled into phase 5
because it must land before/alongside the `users` table; the session-ownership fix (plan §D)
is pulled into phase 6 because `user_id` has to exist on `conversations` first.

Each phase ends with its own verify tasks and an exit task, matching how phases 1 and 2 close
(`[1.21]`–`[1.25]`, `[2.30]`–`[2.34]`).

---

## Phase 5 — Accounts, Auth & Migration Safety (foundation)

Everything else depends on this. Must land first.

| # | Task | Files | Type |
|---|---|---|---|
| 5.1 | Split `_needs_migration()`/`_drop_tables()` so the destructive recreate path only ever targets `conversations`/`messages`/`grammar_feedback` | `services/database.py` | fix |
| 5.2 | Add additive-only migration path (`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD COLUMN`, never drop) for `users`/`daily_usage` | `services/database.py` | fix |
| 5.3 | Create `users` table: `id, email UNIQUE (lowercased), password_hash, display_name, created_at` | `services/database.py` | feature |
| 5.4 | `hash_password`/`verify_password` via `bcrypt` directly (not passlib); reject passwords >72 bytes | `services/auth.py` | feature |
| 5.5 | `create_access_token`/`decode_access_token` via `pyjwt`, 24–72h expiry | `services/auth.py` | feature |
| 5.6 | Add required `JWT_SECRET_KEY` setting, no hardcoded default | `api/config.py` | feature |
| 5.7 | `create_user`, `get_user_by_email` (lowercase-normalized), `get_user_by_id` — thin façade over `services/database.py`, same pattern as `repositories/session_repo.py` | `repositories/user_repo.py` | feature |
| 5.8 | `User` domain model | `models/user.py` | feature |
| 5.9 | `SignupRequest{email,password,display_name}`, `LoginRequest{email,password}`, `TokenResponse{access_token,token_type,user}` | `api/schemas/auth.py` | feature |
| 5.10 | `DuplicateEmailError` (409), `InvalidCredentialsError` (401) | `services/errors.py` | feature |
| 5.11 | `POST /api/v1/auth/signup`, `POST /api/v1/auth/login` | `api/routes/auth.py` | feature |
| 5.12 | Constant-time login: verify against a dummy bcrypt hash when email not found | `api/routes/auth.py` | security |
| 5.13 | `auth_attempts(ip, email, window_date, count)` table + per-IP+email rate limiting on signup/login | `services/database.py`, `api/routes/auth.py` | security |
| 5.14 | `get_current_user(authorization) -> User` dependency: decode JWT, load via `user_repo`, 401 on missing/invalid/expired | `api/dependencies.py` | feature |
| 5.15 | Protect `chat.py`, `sessions.py` with `Depends(get_current_user)` (`lessons.py`/`health.py` stay public; `voice.py` protected in phase 9) | `api/routes/chat.py`, `api/routes/sessions.py` | feature |
| 5.16 | Login/signup `st.form`s | `components/auth_view.py` | feature |
| 5.17 | Add cookie-manager dependency; token persistence read only in `app.py`/`auth_view.py`, never in `api_client.py` | `requirements.txt`, `app.py` | feature |
| 5.18 | `api_client.set_auth_token()` setter + `_auth_headers()` reading module-level state | `api_client.py` | feature |
| 5.19 | 401 special-case in `_request_post`: clear token + cookie, `st.rerun()` back to `auth_view` | `api_client.py` | fix |
| 5.20 | Gate `app.py` routing behind `auth_view` for unauthenticated users | `app.py` | feature |
| 5.21 | Add `bcrypt`, `pyjwt`, cookie-manager component to `requirements.txt`; `JWT_SECRET_KEY`, `JWT_EXPIRY_HOURS` to `.env.example` | `requirements.txt`, `.env.example` | chore |
| 5.22 | Verify: signup creates user; duplicate email → 409; login returns valid JWT; wrong password → 401 | — | test |
| 5.23 | Verify: login response time statistically similar for valid vs. nonexistent email | — | test |
| 5.24 | Verify: expired/tampered JWT → clean 401 → redirect to `auth_view` (not a stuck error banner) | — | test |
| 5.25 | Verify: bump `SCHEMA_VERSION` locally to simulate v3→v4, restart, confirm `users`/`daily_usage` rows survive while conversation tables still migrate cleanly | — | test |
| 5.26 | **Phase 5 exit** — signup → login → lands on (stub) picker, end to end | — | exit |

### Phase 5 detail — what & why (from plan §A, §E)

- **5.1–5.2** Today `_needs_migration()`/`_drop_tables()` recreate `conversations`/`messages`/`grammar_feedback` unconditionally on any `SCHEMA_VERSION` bump — fine while those tables hold disposable transcripts. Once `users`/`daily_usage` share the same DB, an unrelated future bump (v3→v4, for any reason) would silently delete every account and password with no recovery path. Splitting the destructive path to only ever touch the three conversation tables, and giving `users`/`daily_usage` their own additive-only path (`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD COLUMN`, never a drop), closes that. This is a targeted fix, not a move to a migration framework — Alembic etc. is out of scope at this app's size.
- **5.3, 5.7** `users` table + `repositories/user_repo.py` follow the exact thin-façade pattern already used by `repositories/session_repo.py`. Email lookups normalize to lowercase before querying so `A@x.com`/`a@x.com` can't register as two accounts.
- **5.4** `bcrypt` directly, not `passlib[bcrypt]` — passlib is unmaintained and its bundled bcrypt-detection breaks on bcrypt ≥4. Reject passwords over 72 bytes because bcrypt silently truncates beyond that (two different long passwords would otherwise hash identically and both "work").
- **5.5–5.6** JWT via `pyjwt`, 24–72h expiry — no refresh-token complexity needed at this app's scale. `JWT_SECRET_KEY` is required with no hardcoded default, matching how `OPENROUTER_API_KEY` is already treated in `api/config.py`: a default secret would make every deployment's tokens forgeable.
- **5.10** New `AppError` subclasses follow the same pattern as the existing `LessonNotFoundError` etc. in `services/errors.py`.
- **5.12** Login must run at constant time regardless of whether the email exists — verify against a dummy bcrypt hash on a miss, so account existence can't be inferred from response timing.
- **5.13** A per-IP+email attempt counter (reusing the `daily_usage`-style table shape) blunts credential-stuffing against a publicly reachable login endpoint — the app has no other rate limiting today, and auth is the one surface that specifically needs it.
- **5.14–5.15** `chat.py`/`sessions.py` get protected now; `voice.py` is protected too but only once it exists in phase 9. `lessons.py`/`health.py` stay public — they don't expose user-owned data.
- **5.17–5.19** Streamlit has no server-side session concept, so the token needs a cookie-manager component to survive a page refresh. That cookie must be read **only** in `app.py`/`auth_view.py`, never imported into `api_client.py` — doing so would put UI-layer session state inside the HTTP client and silently break the "presentation never touches internals directly" layering this codebase enforces, which `verify_no_service_imports.py` wouldn't catch (it only checks for `services`/`repositories`/`openrouter` imports). Instead `app.py` reads the cookie and calls `api_client.set_auth_token()`; `_auth_headers()` reads that module-level state. `_request_post` today turns every failure into a generic `st.error()` + empty fallback — it must special-case 401 to clear the token+cookie and `st.rerun()` into `auth_view`, otherwise an expired token just shows "temporarily unavailable" forever with no way out except a manual reload.
- **5.20** Gates `app.py`'s routing behind `auth_view` — unauthenticated users see login/signup before the mode/difficulty picker.
- **5.22–5.25** Verify the auth surface end to end: happy/error paths for signup and login, the timing-safety property from 5.12, the 401→redirect flow from 5.19, and the migration-safety property from 5.1–5.2 (simulate a v3→v4 bump, confirm `users`/`daily_usage` survive while conversation tables still migrate cleanly).
- **Accepted tradeoffs** (stated, not silently skipped): the JWT sits in a JS-readable cookie, not an HttpOnly one — acceptable for this low-stakes app, same trust model as the existing `BACKEND_URL` secret. No email-verification step; signup is immediate. Real gaps, fine for this app's stage.

### Phase 5 — how to implement each task

- **5.1** In `services/database.py`, rename today's `_drop_tables()` (`database.py:66-71`, already scoped to `grammar_feedback`/`messages`/`conversations`) to `_drop_conversation_tables()` — its body doesn't change. Split `_init_schema` (`database.py:24-33`) into two independent calls: keep the existing `_needs_migration()`/drop/recreate logic exactly as-is (renamed for clarity, e.g. `_conversation_schema_needs_migration()`), and add a second, always-run call to a new `_ensure_accounts_schema(conn)` (5.2) that never drops anything. `SCHEMA_VERSION` continues to version only the conversation-table shape.
- **5.2** New `_ensure_accounts_schema(conn)` in `database.py`, called unconditionally from `_init_schema` (every `get_connection()`): `CREATE TABLE IF NOT EXISTS users (...)` / `CREATE TABLE IF NOT EXISTS daily_usage (...)` (created in 5.3/7.1). Add a small helper for future columns: `_add_column_if_missing(conn, table, column, coltype)` — check `PRAGMA table_info(table)`, run `ALTER TABLE {table} ADD COLUMN {column} {coltype}` only if absent. No `DROP TABLE` ever touches `users`/`daily_usage`/`auth_attempts` anywhere in the codebase.
- **5.3** Inside `_ensure_accounts_schema`: `CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, display_name TEXT NOT NULL, created_at TEXT NOT NULL)`. Add `create_user(email, password_hash, display_name) -> int`, `get_user_by_email(email) -> dict | None`, `get_user_by_id(user_id) -> dict | None` to `database.py` in the same `get_connection()`/execute/close style as `save_session`/`get_session_summary` (`database.py:136-274`). Always `.strip().lower()` the email before INSERT/SELECT.
- **5.4** `pip install bcrypt`, add to `requirements.txt`/`requirements-api.txt`. New `services/auth.py`:
  ```python
  import bcrypt
  MAX_PASSWORD_BYTES = 72

  def hash_password(password: str) -> str:
      if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
          raise ValueError("Password too long")
      return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

  def verify_password(password: str, password_hash: str) -> bool:
      return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
  ```
- **5.5** `pip install pyjwt`. Same file:
  ```python
  import jwt
  from datetime import datetime, timedelta, timezone

  def create_access_token(user_id: int, secret: str, expiry_hours: int) -> str:
      payload = {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(hours=expiry_hours)}
      return jwt.encode(payload, secret, algorithm="HS256")

  def decode_access_token(token: str, secret: str) -> int:
      payload = jwt.decode(token, secret, algorithms=["HS256"])
      return int(payload["sub"])
  ```
  Let `jwt.ExpiredSignatureError`/`jwt.InvalidTokenError` propagate — 5.14's dependency catches them.
- **5.6** `api/config.py`'s `Settings` (`config.py:10-26`) gains `jwt_secret_key: str` (no default, so pydantic-settings fails startup if unset — same treatment as `openrouter_api_key` today) and `jwt_expiry_hours: int = 48`. Pass them explicitly into `auth.create_access_token`/`decode_access_token` calls from routes/dependencies rather than routing through `apply_to_environ()` (`config.py:35-43`) — that bridge exists for legacy `os.getenv`-at-import modules; `auth.py` is new code and doesn't need it.
- **5.7** New `repositories/user_repo.py`, mirroring `repositories/session_repo.py:1-35` exactly:
  ```python
  from services import database

  class UserRepository:
      def create(self, email: str, password_hash: str, display_name: str) -> int:
          return database.create_user(email.strip().lower(), password_hash, display_name)
      def get_by_email(self, email: str) -> dict | None:
          return database.get_user_by_email(email.strip().lower())
      def get_by_id(self, user_id: int) -> dict | None:
          return database.get_user_by_id(user_id)
  ```
- **5.8** New `models/user.py`: `class User(BaseModel): id: int; email: str; display_name: str; created_at: str` — deliberately no `password_hash` field, so it's safe to embed in `TokenResponse.user`.
- **5.9** New `api/schemas/auth.py` (add `pydantic[email]`'s `email-validator` to requirements for `EmailStr`):
  ```python
  class SignupRequest(BaseModel):
      email: EmailStr
      password: str = Field(min_length=8, max_length=72)
      display_name: str = Field(min_length=1, max_length=100)

  class LoginRequest(BaseModel):
      email: EmailStr
      password: str

  class TokenResponse(BaseModel):
      access_token: str
      token_type: str = "bearer"
      user: User
  ```
- **5.10** `services/errors.py`, same shape as the existing subclasses (`errors.py:14-27`): `class DuplicateEmailError(AppError): status_code = 409; detail = "An account with this email already exists"` and `class InvalidCredentialsError(AppError): status_code = 401; detail = "Invalid email or password"`.
- **5.11** New `api/routes/auth.py`, following the thin-route style of `api/routes/chat.py:12-20`:
  ```python
  router = APIRouter(prefix="/auth", tags=["auth"])

  @router.post("/signup", response_model=TokenResponse, status_code=201)
  def signup(body: SignupRequest, settings=Depends(get_settings)) -> TokenResponse:
      if user_repo.get_by_email(body.email):
          raise DuplicateEmailError()
      password_hash = auth.hash_password(body.password)
      user_id = user_repo.create(body.email, password_hash, body.display_name)
      user = user_repo.get_by_id(user_id)
      token = auth.create_access_token(user_id, settings.jwt_secret_key, settings.jwt_expiry_hours)
      return TokenResponse(access_token=token, user=User(**user))

  @router.post("/login", response_model=TokenResponse)
  def login(body: LoginRequest, request: Request, settings=Depends(get_settings)) -> TokenResponse:
      # rate-limit check (5.13) goes first
      row = user_repo.get_by_email(body.email)
      ok = auth.verify_password(body.password, row["password_hash"] if row else DUMMY_HASH)
      if not row or not ok:
          raise InvalidCredentialsError()
      token = auth.create_access_token(row["id"], settings.jwt_secret_key, settings.jwt_expiry_hours)
      return TokenResponse(access_token=token, user=User(**row))
  ```
  Register with `app.include_router(auth.router, prefix="/api/v1")` in `api/main.py` (alongside `main.py:52-55`).
- **5.12** In `services/auth.py`, precompute once at import: `DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt()).decode("utf-8")`. The login handler above always calls `verify_password` — against the real hash when the row exists, against `DUMMY_HASH` when it doesn't — so a bcrypt round runs either way before `InvalidCredentialsError` is raised.
- **5.13** Add to `_ensure_accounts_schema` (5.2): `CREATE TABLE IF NOT EXISTS auth_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT NOT NULL, email TEXT NOT NULL, window_date TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, UNIQUE(ip, email, window_date))`. New `database.py` function `check_and_increment_auth_attempt(ip, email, max_attempts) -> bool` using `INSERT ... ON CONFLICT(ip,email,window_date) DO UPDATE SET count = count + 1 RETURNING count`, windowed by `datetime.now(timezone.utc).date().isoformat()`. Call it first thing in both `signup`/`login` handlers using `request.client.host`; raise a new 429 `AppError` subclass if over threshold (e.g. 10/day per ip+email).
- **5.14** `api/dependencies.py` (alongside `get_session_repository`, `dependencies.py:8-10`):
  ```python
  def get_current_user(authorization: str | None = Header(default=None), settings: Settings = Depends(get_settings)) -> User:
      if not authorization or not authorization.startswith("Bearer "):
          raise InvalidCredentialsError()
      try:
          user_id = auth.decode_access_token(authorization.removeprefix("Bearer "), settings.jwt_secret_key)
      except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
          raise InvalidCredentialsError()
      row = user_repo.get_by_id(user_id)
      if row is None:
          raise InvalidCredentialsError()
      return User(**row)
  ```
- **5.15** Add `current_user: User = Depends(get_current_user)` as a parameter on every route function in `api/routes/chat.py` (`chat.py:13,18`) and `api/routes/sessions.py` (`sessions.py:16,26,48`). `chat.py` doesn't need to *use* `current_user` yet (ownership wiring is 6.10-6.12); `sessions.py` starts using it immediately once phase 6 lands.
- **5.16** New `components/auth_view.py`:
  ```python
  def render_auth_view() -> None:
      tab_login, tab_signup = st.tabs(["Login", "Sign Up"])
      with tab_login:
          with st.form("login_form"):
              email = st.text_input("Email")
              password = st.text_input("Password", type="password")
              if st.form_submit_button("Login"):
                  result = api_client.login(email, password)
                  if result:
                      _on_authenticated(result)
      with tab_signup:
          with st.form("signup_form"):
              email = st.text_input("Email", key="signup_email")
              password = st.text_input("Password", type="password", key="signup_password")
              display_name = st.text_input("Name")
              if st.form_submit_button("Sign Up"):
                  result = api_client.signup(email, password, display_name)
                  if result:
                      _on_authenticated(result)
  ```
  `_on_authenticated(result)` calls `api_client.set_auth_token(result["access_token"])`, writes the auth cookie (5.17), sets `st.session_state.user = result["user"]`, then `st.rerun()`.
- **5.17** Add `extra-streamlit-components>=0.1.71` to `requirements.txt` (frontend-only). In `app.py`, instantiate `cookie_manager = stx.CookieManager()` once near the top of `main()`; on load, `token = cookie_manager.get("auth_token")` — if present, call `api_client.set_auth_token(token)` before deciding whether to show `auth_view` (a bad/expired token still bounces cleanly through 5.19's 401 handling on the first real API call). On successful login/signup, `auth_view.py` calls `cookie_manager.set("auth_token", token)`.
- **5.18** `api_client.py` gains module-level `_auth_token: str | None = None`, `def set_auth_token(token): global _auth_token; _auth_token = token`, `def _auth_headers() -> dict: return {"Authorization": f"Bearer {_auth_token}"} if _auth_token else {}`. Thread `headers=_auth_headers()` into every `httpx.get`/`httpx.post` inside `_request_get`/`_request_post` (`api_client.py:75,96`) and into the phase-9 multipart/binary helpers.
- **5.19** In `_request_post`'s `except httpx.HTTPStatusError as exc:` branch (`api_client.py:101-102`), add before the generic path: on `exc.response.status_code == 401`, call `set_auth_token(None)`, set `st.session_state["force_logout"] = True`, and let the caller's next render see it. In `app.py`'s `main()`, check `if st.session_state.get("force_logout"): cookie_manager.delete("auth_token"); st.session_state.clear(); st.rerun()` near the top — the cookie can only be cleared from `app.py` since that's where the `CookieManager` instance lives, not from `api_client.py`.
- **5.20** In `app.py`'s `main()`, right after `init_session_state()` (`app.py:36`), add: `if not st.session_state.get("user"): render_auth_view(); return` before `render_sidebar()`. `init_session_state()`'s `defaults` dict (`app.py:13-23`) gains `"user": None`.
- **5.21** Add `bcrypt>=4.1.0`, `pyjwt>=2.8.0`, `email-validator>=2.1.0` to both `requirements.txt` and `requirements-api.txt`; `extra-streamlit-components>=0.1.71` to `requirements.txt` only. Add `JWT_SECRET_KEY=` (blank — force a real value via e.g. `openssl rand -hex 32`) and `JWT_EXPIRY_HOURS=48` to `.env.example` under a new "Auth" section.
- **5.22–5.25** No new production code — write `scripts/verify_phase5.py` in the style of `scripts/verify_phase2_exit.py` (httpx calls against the running API). 5.22: `POST /auth/signup` twice with the same email → 201 then 409; `POST /auth/login` with a wrong password → 401. 5.23: `time.perf_counter()` around several login calls each for an existing vs. a nonexistent email, assert the average delta is small (e.g. <50ms) — proves 5.12. 5.24: hand-craft an expired token (`jwt.encode({"sub":"1","exp":datetime.now(timezone.utc)-timedelta(seconds=1)}, secret)`), call a protected route, assert 401; then manually confirm the Streamlit app bounces to `auth_view` rather than showing a stuck error. 5.25: temporarily set `SCHEMA_VERSION = 3` in `database.py`, restart, confirm `SELECT * FROM users` still returns the pre-existing rows while `conversations` still migrates — then revert the temporary bump.
- **5.26** Manual walkthrough: start both processes, sign up in the Streamlit UI, land on the (stub) picker, refresh the browser tab, confirm still logged in (proves 5.17's cookie round-trip end to end).

---

## Phase 6 — Difficulty Levels, Free Talk Mode & Session Ownership

| # | Task | Files | Type |
|---|---|---|---|
| 6.1 | `difficulty_levels.yaml` — beginner/intermediate/advanced: vocab complexity, pace, correction-strictness | `prompts/difficulty_levels.yaml` | feature |
| 6.2 | `free_talk_context.yaml` — agent picks real-world topics, corrects any mistake | `prompts/free_talk_context.yaml` | feature |
| 6.3 | Add flowing-conversation instruction block (follow-ups, react, pick new topic on stall) | `prompts/system_prompt.yaml` | feature |
| 6.4 | `build_messages(lesson, history, start, difficulty, mode)` — branch free_talk vs lesson context, always append difficulty block | `prompts/prompt_builder.py` | feature |
| 6.5 | `start_conversation`/`send_message` gain `difficulty`, `mode`; `lesson_id` becomes `Optional[str]`, resolved via `lessons.get_lesson()` only when `mode=="lesson"` | `services/conversation.py` | feature |
| 6.6 | Schema: `conversations` gains `user_id` FK, `difficulty TEXT`, `mode TEXT DEFAULT 'lesson'`; `lesson_id`/`lesson_title` nullable (additive, per phase 5's migration path) | `services/database.py` | feature |
| 6.7 | `end_session(lesson_id: str \| None, ..., mode)` skips lesson lookup and uses `lesson_title="Free Talk"` when `mode=="free_talk"` | `services/conversation.py` | fix |
| 6.8 | `SessionListItem`/`SessionDetail`/`Conversation.lesson_id` → `str \| None` | `models/conversation.py` | fix |
| 6.9 | Match nullable `lesson_id` in API schema | `api/schemas/session.py` | fix |
| 6.10 | Thread `user_id` through `end_session`/`SessionRepository.save` | `services/conversation.py`, `repositories/session_repo.py` | security |
| 6.11 | Filter `list_recent()`/`get_summary()` by authenticated `user_id` — ownership enforced at repository/query level (IDOR fix) | `repositories/session_repo.py` | security |
| 6.12 | Pass authenticated `user_id` from routes into service calls | `api/routes/chat.py`, `api/routes/sessions.py` | feature |
| 6.13 | Mode picker (Lesson/Free Talk) → Difficulty picker → lesson picker or straight to chat | `components/mode_picker.py` | feature |
| 6.14 | Sidebar displays mode + difficulty | `sidebar.py` | feature |
| 6.15 | Verify: Free Talk starts without `lesson_id`, agent proactively picks topics | — | test |
| 6.16 | Verify: existing Lesson mode flow unaffected (regression) | — | test |
| 6.17 | **Ownership check**: two accounts, confirm account A's `GET /sessions` never lists account B's session, and `GET /sessions/{b_id}` from A's token 404s (not 200) | — | test |
| 6.18 | **Phase 6 exit** — mode/difficulty picker → Free Talk conversation → save → Arabic-pending summary works end to end | — | exit |

*(Independent of phase 7/8 — can run in parallel with those once phase 5 is merged.)*

### Phase 6 detail — what & why (from plan §B, §D)

- **6.1** `difficulty_levels.yaml` follows the same pattern as the other prompt YAMLs — per level it injects vocabulary complexity, pace, and correction-strictness guidance into the system prompt.
- **6.2** `free_talk_context.yaml` replaces `lesson_context.yaml` when `mode=="free_talk"` — instructs the agent to pick real-world topics itself and correct any mistake, not just one lesson's grammar point.
- **6.3** New instruction block in `system_prompt.yaml`: keep the conversation flowing like a real back-and-forth (follow-ups, react to what was said); if the learner stalls, pick a new topic rather than waiting on them. This is the concrete mechanism behind "natural conversation" — a prompting change, not new infra, consistent with the turn-based-voice decision in §C.
- **6.4** `build_messages` branches free_talk vs lesson context, but always appends the difficulty block regardless of mode — difficulty and mode are independent axes.
- **6.5** `lesson_id` becomes `Optional[str]`, resolved via `lessons.get_lesson()` only when `mode=="lesson"` — Free Talk conversations never touch the lessons table.
- **6.6** `conversations.user_id` FK lands now, not deferred to a later phase, because 6.10–6.11's ownership filtering needs the column to exist before `sessions.py` can filter by it.
- **6.7–6.9 — fix required, not a follow-up.** As drafted, `end_session` calls `lessons.get_lesson(lesson_id)` unconditionally, and `SessionListItem`/`SessionDetail`/`Conversation` all declare `lesson_id: str` as non-optional — Free Talk would crash on save without this. `mode` lets `end_session` skip the lookup and use `lesson_title="Free Talk"` for display instead.
- **6.10–6.12 — this is the IDOR fix.** Auth without ownership is a data leak, not just a missing feature: `conversations` has no owner column today and `list_recent()`/`get_summary()` are global across all sessions. Gating `sessions.py` behind auth *without* this would let every logged-in user list and open every other user's transcripts. Ownership is enforced at the repository/query level (filtered by authenticated `user_id`), not just checked at the route — a route-level-only check can be silently bypassed if a query forgets the filter.
- **6.13–6.14** Picker flow: Mode (Lesson/Free Talk) → Difficulty → lesson picker if Lesson, straight to chat if Free Talk. Sidebar surfaces both so the learner always sees which mode/level they're in.
- **6.17 — the concrete ownership test.** Two accounts, confirm account A's `GET /sessions` never lists account B's session, and `GET /sessions/{b_id}` from A's token 404s (not 200). Per plan §I, this must be explicitly tested, not assumed safe from code review alone.

### Phase 6 — how to implement each task

- **6.1** New `prompts/difficulty_levels.yaml`, one top-level key per level with `vocabulary`/`pace`/`correction_strictness` strings — same shallow-template shape as the existing prompt YAMLs:
  ```yaml
  beginner:
    vocabulary: "Use only simple, everyday words. Avoid idioms."
    pace: "Short sentences. One idea per turn."
    correction_strictness: "Correct only major grammar errors; let minor style slide."
  intermediate: {...}
  advanced: {...}
  ```
  Add `get_difficulty_template(level: str) -> dict` to `prompts/prompt_loader.py`, using the same `@lru_cache` YAML-read pattern already used for `get_lesson_context_template`/`get_system_prompt`.
- **6.2** New `prompts/free_talk_context.yaml`, a single template string with `{student_level}`/`{native_language}` placeholders only (no `{title}`/`{grammar_rules}`/`{vocabulary}` — there's no lesson). Instructs the model to pick a real-world topic itself, correct any grammar mistake (not just one rule), and move the conversation forward on its own initiative rather than announcing "let's move to the next topic." Loader: `get_free_talk_context_template()` in `prompt_loader.py`, same `lru_cache` pattern.
- **6.3** Edit `prompts/system_prompt.yaml` directly — append a new instruction block (plain prose, no code change): ask a follow-up tied to what the learner just said; if the learner stalls or gives a one-word answer, pick a new related topic rather than waiting. Loaded automatically via the existing `get_system_prompt()` call in both modes.
- **6.4** `prompts/prompt_builder.py:10` → `build_messages(lesson: dict | None, history, start=False, difficulty="beginner", mode="lesson")`. Refactor `_build_system_content` (`prompt_builder.py:31-45`) to also append the difficulty block: `difficulty_block = format_difficulty(get_difficulty_template(difficulty))`, returned as `f"{get_system_prompt()}\n\n{lesson_context}\n\n{difficulty_block}"`. Add a sibling `_build_free_talk_content(difficulty)` (same difficulty-block append, but built from `get_free_talk_context_template()` instead of the lesson template) and branch on `mode` at the top of `build_messages`.
- **6.5** `services/conversation.py:12` → `start_conversation(lesson_id: str | None, difficulty: str = "beginner", mode: str = "lesson")`; `conversation.py:25` → `send_message(lesson_id: str | None, messages, user_text, difficulty="beginner", mode="lesson")`. Inside each: `lesson_dict = lessons.get_lesson(lesson_id).model_dump() if mode == "lesson" else None`, then pass `difficulty=difficulty, mode=mode` into `build_messages(...)`.
- **6.6** In `_create_tables`'s conversations DDL (`database.py:76-88`), add `user_id INTEGER, difficulty TEXT, mode TEXT NOT NULL DEFAULT 'lesson'` and drop `NOT NULL` from `lesson_id`/`lesson_title`. Since these three tables still go through the destructive recreate path (5.1), editing the `CREATE TABLE` statement directly is sufficient — bump `SCHEMA_VERSION = 3` (`database.py:12`) to trigger the recreate on next boot. `_ensure_accounts_schema` (5.2) already runs before `_create_tables`, so `users` exists in time for an optional `FOREIGN KEY (user_id) REFERENCES users(id)`.
- **6.7** `services/conversation.py:43` → `end_session(lesson_id: str | None, messages, mistakes, mode: str = "lesson")`. Guard the lookup: `if mode == "free_talk": lesson_dict, lesson_title = None, "Free Talk"` else resolve via `lessons.get_lesson(lesson_id)` as today. Pass `lesson_title` (not `lesson.title`) into both `scoring.calculate_session_summary(..., lesson_title=lesson_title)` and `SessionRepository().save(lesson=lesson_dict or {"id": None, "title": "Free Talk"}, ...)`.
- **6.8–6.9** `models/conversation.py`: `SessionListItem.lesson_id: str` (`conversation.py:43`) → `str | None`; `Conversation.lesson_id` (`conversation.py:67`) → `str | None` (`SessionDetail` inherits `SessionSummary`, not `SessionListItem`, so check whether it needs its own `lesson_id` field added as nullable too — currently `SessionDetail` at `conversation.py:57-62` already redeclares `lesson_id: str`, make that `str | None`). `api/schemas/session.py`'s `SessionCreateRequest.lesson_id` (`session.py:10`) → `str | None = Field(default=None)`, plus add `mode: str = "lesson"` so the route can forward it.
- **6.10–6.12 (the IDOR fix)** `database.py.save_session` (`database.py:136-142`) gains `user_id: int | None`, inserted as a new column value in the conversations INSERT (`database.py:153-173`). `session_repo.py.save` (`session_repo.py:9-24`) forwards `user_id`. `database.list_past_sessions`/`get_session_summary` (`database.py:233,249`) both gain a required `user_id: int` param and add `WHERE user_id = ?` / `WHERE id = ? AND user_id = ?` to their SQL — this is the actual fix, not just a route-level check. `session_repo.py`'s `list_recent`/`get_summary` (`session_repo.py:26,29`) forward `user_id` through. In `api/routes/sessions.py`, add `current_user: User = Depends(get_current_user)` to all three routes (`sessions.py:16,26,48`) and pass `current_user.id` into every call. `conversation.end_session` gains `user_id: int` and forwards it into `SessionRepository().save(...)`.
- **6.13** New `components/mode_picker.py`: `st.radio("Mode", ["Lesson", "Free Talk"])` → `st.radio("Difficulty", ["Beginner", "Intermediate", "Advanced"])`, lowercased into `st.session_state.mode`/`st.session_state.difficulty`. Lesson mode falls through to the existing lesson selectbox in `sidebar.py:57-61`; Free Talk sets `st.session_state.lesson = None` and jumps straight to `conversation_started = True`. Wire into `app.py`'s routing (`app.py:47-54`) ahead of `render_lesson_view()`/`render_chat()`.
- **6.14** In `sidebar.py`'s "Progress" section (near `sidebar.py:69`): `st.caption(f"{st.session_state.mode.title()} · {st.session_state.difficulty.title()}")`.
- **6.15–6.17** 6.15: start Free Talk via the picker, confirm `POST /chat/start` is sent with `lesson_id=None, mode="free_talk"` and the opening assistant message proposes a topic unprompted. 6.16: run the existing lesson-mode flow unchanged and confirm scores/corrections still work — the regression check on 6.4–6.7's branching. 6.17: `POST /auth/signup` twice (users A, B), save one session as each via `POST /sessions`, then as A: `GET /sessions` must not list B's session id, and `GET /sessions/{b_id}` must 404 (from `get_summary`'s `WHERE user_id=?` returning no row), not 200.
- **6.18** Full walkthrough: login → mode picker → Free Talk @ a difficulty → a few chat turns → End Session → summary shows "Free Talk" as the title with no crash from the nullable `lesson_id` path.

---

## Phase 7 — Daily Usage Limit (text turns)

| # | Task | Files | Type |
|---|---|---|---|
| 7.1 | `daily_usage(id, user_id, usage_date, message_count, voice_call_count, updated_at)` — additive per phase 5 | `services/database.py` | feature |
| 7.2 | `DAILY_MESSAGE_LIMIT` (default 20), `DAILY_VOICE_CALL_LIMIT` settings | `api/config.py` | feature |
| 7.3 | `check_and_increment(user_id)` / `check_and_increment_voice(user_id)`; `DailyLimitExceededError` (429, Arabic message, remaining count) | `services/usage.py` | feature |
| 7.4 | Thin façade repo, same pattern as `session_repo.py` | `repositories/usage_repo.py` | feature |
| 7.5 | `get_usage_repository()` DI getter | `api/dependencies.py` | feature |
| 7.6 | Wire `check_and_increment` into the chat-message route | `api/routes/chat.py` | feature |
| 7.7 | `max_length` caps: `messages` list (100), `Message.content` (~2000 chars) | `api/schemas/chat.py` | fix |
| 7.8 | Trailing-window history truncation so long sessions don't blow past the cost model | `prompts/prompt_builder.py` | fix |
| 7.9 | `GET /api/v1/usage/today` | `api/routes/usage.py` | feature |
| 7.10 | Sidebar: remaining-messages-today display via new endpoint | `sidebar.py` | feature |
| 7.11 | Handle 429: Arabic message, disable input for the day via session-state flag | `api_client.py`, `components/chat.py` | feature |
| 7.12 | Verify: looping messages past `DAILY_MESSAGE_LIMIT` → 429 with correct remaining-count body | — | test |
| 7.13 | Verify: usage counter persists across logout/login on the same day | — | test |
| 7.14 | **Phase 7 exit** — hit the limit mid-conversation, confirm graceful block + Arabic messaging | — | exit |

*(Independent of phase 6/8 — can run in parallel once phase 5 is merged.)*

### Phase 7 detail — what & why (from plan §D)

- **7.1** `daily_usage` is created additive per phase 5's migration path (5.1–5.2) — so an unrelated future schema bump can't wipe usage counters any more than it can wipe accounts.
- **7.2** `DAILY_MESSAGE_LIMIT` defaults to **20**, not a rounder 40 — see the cost note below; it's a deliberately conservative starting point.
- **7.3–7.5** `check_and_increment`/`check_and_increment_voice` (the voice half is wired in phase 9 once `services/voice.py` exists) raise `DailyLimitExceededError` (429, Arabic-first message, remaining count in the body) when at limit. The repo follows the same façade pattern as `session_repo.py`.
- **7.7–7.8 — bounds the cost per turn, not just the turn count.** As drafted, `ChatMessageRequest` has no cap on message-history length or per-message content length, and the client resends the full history every turn — so "N messages/day" understates real cost, since prompt size grows quadratically across a long session. `max_length` caps (`messages` ≤100, `content` ≤~2000 chars) plus trailing-window truncation in `prompt_builder` keep the cost model in 7.2 honest for long-running sessions.
- **7.9** `/usage/today` exists because the sidebar's "remaining messages today" needs a real source — client-side counting would drift across devices/tabs. The 429 body also carries the remaining count (0) so the two surfaces stay consistent.
- **7.11** 429 handling reuses the same error-handling path `api_client.py` already uses for other failures, and disables input for the day via a session-state flag rather than a client-side counter (which could drift, per 7.9).
- **Cost sanity check** (informs 7.2's default): at `DAILY_MESSAGE_LIMIT=20` with the 7.7–7.8 bounds, ballpark $0.12–0.18/user/day across OpenRouter LLM + Deepgram Nova-2 STT + Aura TTS — roughly $4–5/user/month. Deliberately conservative; it's just an env var to raise later once real usage is observed.

### Phase 7 — how to implement each task

- **7.1** Add to `_ensure_accounts_schema` (5.2): `CREATE TABLE IF NOT EXISTS daily_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, usage_date TEXT NOT NULL, message_count INTEGER NOT NULL DEFAULT 0, voice_call_count INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL, UNIQUE(user_id, usage_date))`.
- **7.2** `api/config.py`'s `Settings`: `daily_message_limit: int = 20`, `daily_voice_call_limit: int = 20`.
- **7.3** New `services/usage.py`:
  ```python
  def check_and_increment(user_id: int, limit: int) -> int:
      today = datetime.now(timezone.utc).date().isoformat()
      row = database.get_or_create_usage_row(user_id, today)
      if row["message_count"] >= limit:
          raise DailyLimitExceededError(remaining=0)
      database.increment_usage(user_id, today, field="message_count")
      return limit - row["message_count"] - 1

  def check_and_increment_voice(user_id: int, limit: int) -> int:
      ...  # identical shape, field="voice_call_count" (wired in phase 9)
  ```
  `DailyLimitExceededError` in `services/errors.py`: `status_code = 429`, constructor takes `remaining: int`, Arabic-first message (e.g. "لقد وصلت إلى الحد اليومي للرسائل. حاول مرة أخرى غداً."). Since `AppError.detail` is a plain string and the single `exception_handler` in `api/main.py:58-60` only emits `{"detail": ...}`, either embed the remaining count in the message text or extend that handler with an `isinstance(exc, DailyLimitExceededError)` branch that adds a `remaining` key to the JSON body.
- **7.4** New `repositories/usage_repo.py` mirroring `session_repo.py`'s facade style, wrapping `database.get_or_create_usage_row`/`increment_usage`/`get_usage_today`.
- **7.5** `api/dependencies.py`, same `@lru_cache` pattern as `get_session_repository` (`dependencies.py:8-10`): `def get_usage_repository() -> UsageRepository: return UsageRepository()`.
- **7.6** `api/routes/chat.py`'s `send_chat_message` (`chat.py:18`) gains `current_user`, `settings`, `usage_repo` dependencies; call `usage.check_and_increment(current_user.id, settings.daily_message_limit)` **before** calling `conversation.send_message(...)` — failing fast avoids spending on the LLM call when already at the limit.
- **7.7** `api/schemas/chat.py`'s `ChatMessageRequest.messages` (`chat.py:15`) → `Field(min_length=1, max_length=100)`. `models/conversation.py`'s `Message.content` (`conversation.py:14`) gains `Field(max_length=2000)` — this caps both the chat and session schemas since both reuse `Message`.
- **7.8** In `prompt_builder.build_messages`'s history loop (`prompt_builder.py:18-19`), slice before appending: `history = history[-MAX_HISTORY_TURNS:]` with a module constant `MAX_HISTORY_TURNS = 20` — truncate before building the messages list so token cost per call stays bounded regardless of client-reported history length.
- **7.9** New `api/routes/usage.py`:
  ```python
  router = APIRouter(prefix="/usage", tags=["usage"])

  @router.get("/today")
  def get_usage_today(current_user=Depends(get_current_user), settings=Depends(get_settings), repo=Depends(get_usage_repository)) -> dict:
      row = repo.get_today(current_user.id)
      return {
          "messages_used": row["message_count"], "messages_limit": settings.daily_message_limit,
          "voice_used": row["voice_call_count"], "voice_limit": settings.daily_voice_call_limit,
      }
  ```
  Register alongside the other routers in `api/main.py`.
- **7.10** `sidebar.py`, near the Progress section: new `api_client.get_usage_today() -> dict` (using the existing `_request_get` helper), then `st.caption(f"Messages today: {usage['messages_used']}/{usage['messages_limit']}")`.
- **7.11** Special-case 429 in `_request_post` the same way 5.19 special-cases 401: set `st.session_state["daily_limit_reached"] = True`, let `_error_detail` surface the Arabic message via the existing `st.error()` path. `components/chat.py`'s `render_chat` (`chat.py:11`) checks `if st.session_state.get("daily_limit_reached"): st.warning(...); return` before rendering `st.chat_input`, disabling input for the rest of the day.
- **7.12–7.13** 7.12: script logs in, loops `POST /chat/message` `DAILY_MESSAGE_LIMIT + 1` times, asserts the last call is 429 with `remaining: 0` in the body. 7.13: increment usage, drop the client's in-memory token (simulating logout), log in again same day, `GET /usage/today` still shows the prior count — proves persistence is server-side (`user_id`+`usage_date`), not client `st.session_state`.
- **7.14** Mid-conversation, hit the limit, confirm `st.chat_input` disables with the Arabic message rather than a generic error banner.

---

## Phase 8 — Arabic-First UI Localization

| # | Task | Files | Type |
|---|---|---|---|
| 8.1 | Replace the two hardcoded English recommendation strings with Arabic | `services/scoring.py` | feature |
| 8.2 | Arabic labels/chrome | `sidebar.py` | feature |
| 8.3 | Arabic labels/chrome | `summary.py` | feature |
| 8.4 | Arabic-primary explanation styling (Arabic already present, promote visually) | `components/correction_card.py` | feature |
| 8.5 | Remaining hardcoded English chrome strings → Arabic | `components/chat.py`, other `components/*.py` | feature |
| 8.6 | Scoped RTL CSS (`direction:rtl; text-align:right`) on Arabic-text containers only (sidebar, summary, correction card's Arabic block) — not app-wide | `components/*.py` | feature |
| 8.7 | Verify: chat bubbles/mic controls stay LTR; Arabic chrome renders RTL correctly | — | test |
| 8.8 | **Phase 8 exit** — full Arabic chrome walkthrough | — | exit |

*(Independent — can run in parallel with phase 6/7 once phase 5 is merged, per plan §H.5.)*

### Phase 8 detail — what & why (from plan §F)

- **8.1–8.5** Scope is all *learner-facing chrome* — buttons, headers, sidebar, summary, recommendation text — not the English-practice content itself; chat messages and lesson examples stay English, since practicing English is the point of the app. No i18n/translation-layer framework is introduced: this app has one audience and one target UI language, so a full i18n system would be unused abstraction (YAGNI), consistent with existing project conventions — strings are just replaced in place.
- **8.4** Corrections already carry both languages; this promotes the Arabic explanation to visually primary rather than adding new content.
- **8.6** RTL CSS (`direction: rtl; text-align: right`) is scoped only to Arabic-text containers (sidebar, summary, correction card's Arabic block) — deliberately **not** applied app-wide, because chat bubbles and mic controls must stay LTR. A blanket app-wide `rtl` would break the voice/text input controls added in phase 9.

### Phase 8 — how to implement each task

- **8.1** In `services/scoring.py`, replace the two hardcoded recommendation strings ("Practice {lesson} again tomorrow." / "Excellent work! Try a harder lesson next.") with Arabic equivalents, e.g. `f"راجع {lesson_title} مرة أخرى غداً."` / `"عمل ممتاز! جرّب درساً أصعب في المرة القادمة."`. The same two strings are duplicated client-side in `components/summary.py`'s `_local_preview_summary` (`summary.py:57,59`) — update them to match so the API path and the offline-fallback path stay consistent.
- **8.2–8.3** Direct string replacement of the English literals already in these files. `sidebar.py`: `"📚 English Tutor"` (48), `"Choose a lesson"` (58), `"Progress"` (69), `"Grammar Score"` (72), `"Common mistakes"` (75), `"Vocabulary"` (85), `"End Session"` (92), `"Past Sessions"` (96), `"Exchanges:"`/`"Mistakes:"`/`"Vocabulary:"`/`"Mistake types:"` (34-40). `summary.py`: `"Session Summary"` (115), `"Grammar Score"`/`"Exchanges"`/`"Mistakes"` (126-128), `"Vocabulary"` (130), `"No vocabulary tracked yet."` (134), `"Common Mistakes"` (136), `"No mistakes — great job!"` (141), `"Recommendation"` (143), `"Start New Session"` (147). Only the `st.*` display strings change — dict/variable keys and DB column names stay in English.
- **8.4** `components/correction_card.py` already renders both languages (`correction_card.py:14-17`), English first. Reorder so the Arabic explanation renders first/most prominent — swap the English/Arabic markdown lines, promote the Arabic line's styling (e.g. `st.markdown(f"**{data.get('arabic_explanation','')}**")`) and demote the English line to `st.caption(...)`. The wrong/correct sentence lines (14-15) stay as-is — that's the English practice content, not chrome.
- **8.5** Sweep remaining English literals not covered by 8.2–8.4: `components/chat.py`'s `"Please select a lesson from the sidebar."` (14) and `"Type your answer in English..."` (28), `app.py`'s backend-unreachable warning (40-44). Translate each in place.
- **8.6** Inject a small `unsafe_allow_html=True` `<style>` block or per-string `<div dir="rtl" style="text-align:right">` wrapper only inside the sidebar/summary/correction-card render functions — not in `app.py` globally. Example: `st.markdown(f'<div dir="rtl">{arabic_text}</div>', unsafe_allow_html=True)` for the specific Arabic-explanation line in `correction_card.py`. Never touch `components/chat.py`'s chat bubbles or the phase-9 mic/audio controls.
- **8.7** Manual visual check: chat bubbles and the mic button stay left-to-right; sidebar, summary, and the correction card's Arabic block render right-to-left and right-aligned.
- **8.8** Full Arabic-chrome walkthrough: every non-practice-content string reads in Arabic, RTL renders correctly in the three scoped areas, nothing else visually broke.

---

## Phase 9 — Voice Pipeline (Deepgram STT/TTS)

Depends on phase 6 (chat endpoints) and phase 7 (usage-limiting infra) — the voice-specific
counters below depend on `services/usage.py` existing.

| # | Task | Files | Type |
|---|---|---|---|
| 9.1 | Add `DEEPGRAM_API_KEY` setting | `api/config.py`, `.env.example` | feature |
| 9.2 | `transcribe_audio(audio_bytes, mimetype) -> str` — `POST /v1/listen?model=nova-2&smart_format=true`, raw bytes body (not multipart) | `services/voice.py` | feature |
| 9.3 | `synthesize_speech(text, voice="aura-asteria-en", language="en") -> bytes` — `POST /v1/speak`, JSON body; check Deepgram's Arabic Aura coverage, fall back to browser `speechSynthesis` for Arabic if unavailable | `services/voice.py` | feature |
| 9.4 | `VoiceTranscriptionError` (502), `VoiceSynthesisError` (502) | `services/errors.py` | feature |
| 9.5 | Voice request/response schemas | `api/schemas/voice.py` | feature |
| 9.6 | `POST /api/v1/voice/transcribe` (multipart upload → forward raw bytes to Deepgram), `POST /api/v1/voice/speak` — both auth-protected | `api/routes/voice.py` | feature |
| 9.7 | Wire both endpoints to `check_and_increment_voice` — independently metered from the text limit (not optional, per plan §C) | `api/routes/voice.py` | feature |
| 9.8 | Schema-layer caps: audio upload ≤10MB/60s, TTS input ≤500 chars | `api/schemas/voice.py` | security |
| 9.9 | Multipart-upload helper (transcribe) + raw-bytes-response helper (speak), separate from the existing JSON `_request_post` path | `api_client.py` | feature |
| 9.10 | `transcribe_audio()`, `synthesize_speech()` wrapper methods | `api_client.py` | feature |
| 9.11 | Add `streamlit-mic-recorder` dependency | `requirements.txt` | chore |
| 9.12 | Push-to-talk button alongside existing `st.chat_input()` (kept as fallback); flow: record → transcribe → `send_message()` → `synthesize_speech(reply,"en")` → `st.audio(autoplay=True)` | `components/chat.py` | feature |
| 9.13 | "🔊 استمع" button → `synthesize_speech(text, "ar")` | `components/correction_card.py` | feature |
| 9.14 | Verify: multipart-upload a sample WAV to `/voice/transcribe`, confirm text returned | — | test |
| 9.15 | Verify: `/voice/speak` returns playable audio bytes | — | test |
| 9.16 | Verify: both fail with a clean 429 once `DAILY_VOICE_CALL_LIMIT` is hit, independent of the text message limit | — | test |
| 9.17 | Verify: repeatedly tapping "استمع" moves the voice counter, not the text counter | — | test |
| 9.18 | **Phase 9 exit** — record voice → hear reply → see Arabic correction card with working listen button | — | exit |

### Phase 9 detail — what & why (from plan §C)

- **9.1** OpenRouter (current LLM provider) has no audio endpoints — voice needs its own Deepgram key so the text-conversation LLM call is untouched.
- **9.2** Deepgram takes raw audio bytes as the POST body, not multipart form-data like OpenAI's endpoint — request-building differs from a Whisper-style integration. Hand-roll with `httpx` (no new SDK) matching the existing `services/openrouter.py` pattern.
- **9.3** Nova-2 (STT) + Aura (TTS) = one provider/one key, cheaper per-minute than Whisper on STT. Confirm Aura's Arabic voice coverage during implementation; if no Arabic Aura voice exists, fall back to browser `speechSynthesis` for that one case only — keep the English TTS path on Deepgram.
- **9.4** New error classes join the existing `LLMError` family so voice failures surface as clean 502s (consistent handling), not unhandled exceptions.
- **9.6** `/voice/transcribe` uploads as multipart from Streamlit → FastAPI reads the raw bytes off the upload and forwards them as Deepgram's request body. Both endpoints auth-protected (unlike `lessons.py`/`health.py`, which stay public) — voice reuses the same auth model as chat/sessions.
- **9.7 — not optional.** `/voice/speak` is directly reachable outside any chat turn (the correction-card listen button calls it standalone), and `/voice/transcribe` is billed per audio minute. Bundling that cost under the per-turn text limit only holds if voice is unreachable outside a turn — it isn't. Without an independent `voice_call_count` counter, a user repeatedly tapping "استمع" buys unbounded TTS with zero counter movement.
- **9.8** Schema-layer caps (audio ≤10MB/60s, TTS text ≤500 chars) close that abuse path without constraining legitimate use — corrections are already short.
- **9.9** `_request_post` in `api_client.py` only sends/expects JSON today. Transcribe needs a multipart upload, speak needs a raw-bytes response — neither fits the JSON path, so each gets its own helper rather than overloading it.
- **9.12** `st.chat_input()` is kept, not replaced — an accessibility/fallback path. Voice reuses the *same* `send_message()` call as text turns rather than a parallel voice-only pipeline, so difficulty/mode/history logic isn't duplicated.
- **9.13** The listen button reuses `/voice/speak` directly — ties the voice feature and the Arabic-localization requirement (phase 8) together with no extra infrastructure.
- **9.14–9.17** Mirror plan §I's voice verification: sample-WAV transcribe round-trip, playable `/voice/speak` bytes, both endpoints 429 independently of the text limit once `DAILY_VOICE_CALL_LIMIT` is hit, and the listen button specifically must move the *voice* counter, not the text one (this is the concrete regression test for 9.7's reasoning).

### Phase 9 — how to implement each task

- **9.1** `api/config.py`'s `Settings`: `deepgram_api_key: str` (no default — required, same treatment as `jwt_secret_key`/`openrouter_api_key`). Add `DEEPGRAM_API_KEY=your_deepgram_key_here` to `.env.example`.
- **9.2** New `services/voice.py`, matching `services/openrouter.py`'s hand-rolled `httpx` style (`openrouter.py:17-44`) exactly:
  ```python
  import httpx
  from services.errors import VoiceTranscriptionError

  DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

  def transcribe_audio(audio_bytes: bytes, mimetype: str) -> str:
      try:
          response = httpx.post(
              "https://api.deepgram.com/v1/listen",
              params={"model": "nova-2", "smart_format": "true"},
              headers={"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": mimetype},
              content=audio_bytes,
              timeout=30.0,
          )
          response.raise_for_status()
          return response.json()["results"]["channels"][0]["alternatives"][0]["transcript"]
      except httpx.TimeoutException:
          raise VoiceTranscriptionError("Transcription timed out.")
      except (httpx.HTTPStatusError, httpx.RequestError, KeyError, IndexError):
          raise VoiceTranscriptionError("Could not transcribe audio.")
  ```
  Note the raw-bytes-as-body request shape — deliberately unlike a multipart Whisper-style call.
- **9.3** Same file:
  ```python
  def synthesize_speech(text: str, voice: str = "aura-asteria-en") -> bytes:
      try:
          response = httpx.post(
              "https://api.deepgram.com/v1/speak",
              params={"model": voice},
              headers={"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": "application/json"},
              json={"text": text},
              timeout=30.0,
          )
          response.raise_for_status()
          return response.content
      except httpx.TimeoutException:
          raise VoiceSynthesisError("Speech synthesis timed out.")
      except (httpx.HTTPStatusError, httpx.RequestError):
          raise VoiceSynthesisError("Could not synthesize speech.")
  ```
  Before wiring 9.13, check Deepgram's current Aura model list for an Arabic voice. If none exists, keep `voice.py` Deepgram-only and put the fallback branch in the caller: `api_client.synthesize_speech` returns `None` for `language == "ar"` if no Arabic Aura voice is configured, and `correction_card.py`'s listen button falls back to `st.components.v1.html` calling `window.speechSynthesis.speak(new SpeechSynthesisUtterance(text))` with `utterance.lang = "ar-SA"`.
- **9.4** `services/errors.py`: `class VoiceTranscriptionError(AppError): status_code = 502; detail = "Could not transcribe your recording. Please try again."` and `class VoiceSynthesisError(AppError): status_code = 502; detail = "Could not generate speech. Please try again."` — same family/shape as `LLMError` (`errors.py:29-39`).
- **9.5** New `api/schemas/voice.py`:
  ```python
  class TranscribeResponse(BaseModel):
      text: str

  class SpeakRequest(BaseModel):
      text: str = Field(min_length=1, max_length=500)
      language: Literal["en", "ar"] = "en"
  ```
  The transcribe request itself isn't a JSON body — it's a multipart file upload handled via FastAPI's `UploadFile`, so it needs no request schema.
- **9.6** New `api/routes/voice.py`:
  ```python
  router = APIRouter(prefix="/voice", tags=["voice"])

  @router.post("/transcribe", response_model=TranscribeResponse)
  async def transcribe(file: UploadFile, current_user=Depends(get_current_user), settings=Depends(get_settings), usage_repo=Depends(get_usage_repository)) -> TranscribeResponse:
      usage.check_and_increment_voice(current_user.id, settings.daily_voice_call_limit)
      audio_bytes = await file.read()
      text = voice_service.transcribe_audio(audio_bytes, file.content_type or "audio/wav")
      return TranscribeResponse(text=text)

  @router.post("/speak")
  def speak(body: SpeakRequest, current_user=Depends(get_current_user), settings=Depends(get_settings), usage_repo=Depends(get_usage_repository)) -> Response:
      usage.check_and_increment_voice(current_user.id, settings.daily_voice_call_limit)
      audio = voice_service.synthesize_speech(body.text)
      return Response(content=audio, media_type="audio/mpeg")
  ```
  Register in `api/main.py` alongside the other routers.
- **9.7** Already realized by 9.6's two `usage.check_and_increment_voice` calls — the point is each endpoint meters itself independently, so `correction_card.py`'s standalone listen button (9.13), which hits `/voice/speak` outside any chat turn, still counts.
- **9.8** `SpeakRequest.text` is already capped at 500 (9.5). For uploads, FastAPI's `UploadFile` has no built-in size cap — add a manual check in `transcribe`: `if file.size and file.size > 10 * 1024 * 1024: raise VoiceTranscriptionError("Recording too large (max 10MB).")` before `await file.read()`. Bound duration at the source too via the mic-recorder's max-time setting (9.11/9.12).
- **9.9** `api_client.py`, two new helpers alongside `_request_get`/`_request_post` (`api_client.py:66-105`):
  ```python
  def _request_multipart(path, *, files, timeout, fallback):
      try:
          response = httpx.post(_url(path), files=files, headers=_auth_headers(), timeout=timeout)
          response.raise_for_status()
          return response.json()
      except httpx.TimeoutException:
          _show_error(REQUEST_TIMEOUT_MESSAGE)
      except httpx.HTTPStatusError as exc:
          _show_error(_error_detail(exc.response))
      except httpx.RequestError:
          _show_error(BACKEND_UNAVAILABLE)
      return fallback

  def _request_binary(path, *, json, timeout, fallback):
      try:
          response = httpx.post(_url(path), json=json, headers=_auth_headers(), timeout=timeout)
          response.raise_for_status()
          return response.content
      except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError):
          _show_error(REQUEST_TIMEOUT_MESSAGE)
      return fallback
  ```
  Neither fits the existing JSON-in/JSON-out `_request_post`, so they're separate rather than an overload.
- **9.10** `api_client.py`:
  ```python
  def transcribe_audio(audio_bytes: bytes) -> str | None:
      data = _request_multipart("/api/v1/voice/transcribe", files={"file": ("recording.wav", audio_bytes, "audio/wav")}, timeout=CHAT_TIMEOUT, fallback=None)
      return data.get("text") if data else None

  def synthesize_speech(text: str, language: str = "en") -> bytes | None:
      return _request_binary("/api/v1/voice/speak", json={"text": text, "language": language}, timeout=CHAT_TIMEOUT, fallback=None)
  ```
- **9.11** Add `streamlit-mic-recorder>=0.0.8` to `requirements.txt` only (frontend-only, not `requirements-api.txt`).
- **9.12** `components/chat.py`, alongside the existing `st.chat_input` (`chat.py:28`):
  ```python
  from streamlit_mic_recorder import mic_recorder

  audio = mic_recorder(start_prompt="🎙️ Record", stop_prompt="⏹ Stop", key="voice_input")
  if audio and audio.get("bytes"):
      text = api_client.transcribe_audio(audio["bytes"])
      if text:
          _handle_user_message(text, lesson)  # same path as typed input — no parallel pipeline
  ```
  Inside `_handle_user_message` (`chat.py:54-85`), right after the assistant message is appended, add: `audio_reply = api_client.synthesize_speech(result["reply"], "en"); if audio_reply: st.audio(audio_reply, autoplay=True)`. `st.chat_input` is kept as-is, not removed — the accessibility/fallback path.
- **9.13** `components/correction_card.py`, inside the `for item in feedback:` loop (`correction_card.py:9-20`), after the tip line: switch to `for idx, item in enumerate(feedback):` (unique widget keys are required in a loop) and add `if st.button("🔊 استمع", key=f"listen_{idx}"): audio = api_client.synthesize_speech(data.get('arabic_explanation', ''), 'ar'); if audio: st.audio(audio, autoplay=True)`.
- **9.14–9.17** 9.14: `curl -F file=@sample.wav http://localhost:8000/api/v1/voice/transcribe -H "Authorization: Bearer $TOKEN"`, assert non-empty `text`. 9.15: `curl -X POST .../voice/speak -d '{"text":"hello","language":"en"}' -o out.mp3`, confirm nonzero-size valid audio. 9.16: loop `/voice/speak` past `DAILY_VOICE_CALL_LIMIT` → 429, then confirm `/chat/message` still works — proves independence from the text counter. 9.17: tap the correction-card listen button `DAILY_VOICE_CALL_LIMIT` times, confirm 429, then query `/usage/today` before/after to confirm only `voice_used` moved, not `messages_used`.
- **9.18** Record a voice message, hear the spoken reply autoplay, see an Arabic correction card, tap "استمع", hear the Arabic explanation play.

---

## Phase 10 — Full System Integration & Exit Verification

| # | Task | Type |
|---|---|---|
| 10.1 | Full backend walkthrough: signup → login → Free Talk @ beginner → deliberate grammar mistake → Arabic correction confirmed → loop past `DAILY_MESSAGE_LIMIT` → 429 with correct remaining-count body | test |
| 10.2 | Re-run `scripts/verify_no_service_imports.py` + phase1/phase2 verify scripts — confirm new `auth_view.py`/voice components go through `api_client.py` only, and the cookie-manager component is never imported into `api_client.py` | test |
| 10.3 | Full frontend walkthrough: signup → mode/difficulty picker → Free Talk → record voice → hear reply → Arabic correction card + listen button → End Session → Arabic summary → log out/in → daily counter persists | test |
| 10.4 | Update `README.md` — new env vars, two-provider setup (OpenRouter + Deepgram), auth flow | docs |
| 10.5 | Confirm `.env.example` completeness: `DEEPGRAM_API_KEY`, `JWT_SECRET_KEY`, `JWT_EXPIRY_HOURS`, `DAILY_MESSAGE_LIMIT`, `DAILY_VOICE_CALL_LIMIT` | chore |
| 10.6 | **Phase 10 exit** — sign-off checklist complete | exit |

### Phase 10 detail — what & why (from plan §H, §I)

- **10.1, 10.3** These walkthroughs deliberately chain every phase in one pass, in dependency order: signup→login proves phase 5, Free Talk @ beginner proves phase 6, the Arabic correction proves phase 8, looping past `DAILY_MESSAGE_LIMIT` proves phase 7, the voice round-trip proves phase 9. The point is to prove the phases *compose* — each phase's own exit test already proves it works in isolation; this is the one pass that proves nothing broke when they're layered together (e.g. usage limiting still firing correctly once voice calls are also incrementing counters).
- **10.2** Re-running `verify_no_service_imports.py` plus the phase 1/2 verify scripts confirms the new `auth_view.py`/voice components still route through `api_client.py` only, and specifically that the cookie-manager component (5.17) is never imported into `api_client.py` itself. This mechanically re-checks the layering rule from §A that a plain code review could miss, since the automated check doesn't know about cookie-managers by name — it just checks import boundaries.
- **10.4–10.5** New env vars land piecemeal across phases 5 (`JWT_SECRET_KEY`, `JWT_EXPIRY_HOURS`), 7 (`DAILY_MESSAGE_LIMIT`, `DAILY_VOICE_CALL_LIMIT`), and 9 (`DEEPGRAM_API_KEY`) — this task is the single point where `.env.example`/`README.md` are checked for completeness against all of them at once, rather than trusting each phase to have remembered its own.

### Phase 10 — how to implement each task

- **10.1** Script (httpx or `curl` chain) hitting the live API in dependency order: `POST /auth/signup` → `POST /auth/login` → `POST /chat/start` with `mode="free_talk", difficulty="beginner"` → `POST /chat/message` with a deliberate grammar mistake, assert `corrections[0].arabic_explanation` is non-empty → loop `/chat/message` past `DAILY_MESSAGE_LIMIT`, assert the final call is 429 with the correct `remaining: 0` body shape from 7.3.
- **10.2** Run `python scripts/verify_no_service_imports.py` — extend its grep patterns (it currently only flags `services`/`repositories`/`openrouter` imports, per `docs/PROJECT_BRAIN.md` §14) if needed so it also can't miss a stray import in the new `components/auth_view.py` or the mic-recorder code in `chat.py`. Also re-run `scripts/verify_phase1.py`/`verify_phase2.py`/`verify_phase2_exit.py` as regression checks. Manually `git diff` `api_client.py` to confirm `extra_streamlit_components` (the cookie manager, 5.17) never got imported there — that's the one thing the automated script can't catch, since it doesn't know about cookie-manager libraries by name.
- **10.3** Manual end-to-end walkthrough in the Streamlit UI, in the exact sequence listed in the table: signup → mode/difficulty picker → Free Talk → record voice → hear reply → Arabic correction card + listen button → End Session → Arabic summary → log out (or close the tab) → log back in → confirm the daily counter (7.9's `/usage/today`) persisted across the session boundary.
- **10.4** Update `README.md`'s setup/env-var section: document `DEEPGRAM_API_KEY` alongside the existing `OPENROUTER_API_KEY` as the two required provider keys, add the auth flow (signup/login before anything else works) to the quick-start steps, and note that `JWT_SECRET_KEY` must be generated per-deployment (e.g. `openssl rand -hex 32`) rather than left blank or copied between environments.
- **10.5** Diff every setting added across phases 5/7/9 against `.env.example`'s current contents: `DEEPGRAM_API_KEY`, `JWT_SECRET_KEY`, `JWT_EXPIRY_HOURS`, `DAILY_MESSAGE_LIMIT`, `DAILY_VOICE_CALL_LIMIT` — add whichever are still missing, in the same `# Section` comment style `.env.example` already uses (`.env.example:1,6,10`).
- **10.6** Sign-off checklist: each phase's own exit task (5.26, 6.18, 7.14, 8.8, 9.18) already passed individually; 10.1–10.5 confirm they still hold layered together in one continuous pass.

---

## Summary

| Phase | Theme | Task count | Depends on |
|---|---|---|---|
| 5 | Accounts, auth, migration safety | 26 | — (foundation) |
| 6 | Difficulty + Free Talk + ownership fix | 18 | 5 |
| 7 | Daily usage limit (text) | 14 | 5 |
| 8 | Arabic UI localization | 8 | 5 |
| 9 | Voice pipeline (Deepgram) | 18 | 6, 7 |
| 10 | Integration & exit verification | 6 | 6, 7, 8, 9 |

Phases 6, 7, 8 can run in parallel once phase 5 merges (plan §H.5). Phase 9 must wait on both
6 (chat endpoints it reuses) and 7 (usage infra its voice counters depend on).
