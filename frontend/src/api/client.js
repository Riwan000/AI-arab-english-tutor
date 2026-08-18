// Thin fetch wrapper: attaches the bearer token, throws on non-2xx with the
// parsed {detail} error body FastAPI/AppError always returns (see
// api/main.py's AppError handler).

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TOKEN_STORAGE_KEY = "englishTutor.accessToken";

export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function storeToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

// FastAPI validation errors (422) send `detail` as an array of
// {type, loc, msg, ...} objects rather than a string — flatten those into
// something safe to render directly in JSX.
function formatDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || JSON.stringify(item)).join("; ");
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return String(detail);
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(formatDetail(detail));
    this.status = status;
    this.detail = detail;
  }
}

/**
 * @param {string} path - e.g. "/api/v1/lessons"
 * @param {object} [opts]
 * @param {string} [opts.method]
 * @param {object} [opts.body] - JSON body, auto-stringified (skip for FormData)
 * @param {FormData} [opts.formData] - multipart body
 * @param {string} [opts.token] - bearer token; defaults to the stored token
 * @param {boolean} [opts.raw] - if true, resolve with the raw Response instead of parsed JSON
 */
export async function apiFetch(path, opts = {}) {
  const { method = "GET", body, formData, token, raw = false } = opts;
  const headers = {};
  const authToken = token !== undefined ? token : getStoredToken();
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  let requestBody;
  if (formData) {
    requestBody = formData; // browser sets multipart Content-Type + boundary
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: requestBody,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const parsed = await response.json();
      detail = parsed.detail ?? detail;
    } catch {
      // body wasn't JSON — fall back to statusText
    }
    if (response.status === 401 && !path.includes("/auth/login") && !path.includes("/auth/signup")) {
      storeToken(null);
      localStorage.removeItem("englishTutor.user");
      window.dispatchEvent(new Event("auth:unauthorized"));
    }
    throw new ApiError(response.status, detail);
  }

  if (raw) return response;
  if (response.status === 204) return null;
  return response.json();
}

export const auth = {
  signup: (email, password, display_name) =>
    apiFetch("/api/v1/auth/signup", { method: "POST", body: { email, password, display_name } }),
  login: (email, password) =>
    apiFetch("/api/v1/auth/login", { method: "POST", body: { email, password } }),
};

export const lessons = {
  list: () => apiFetch("/api/v1/lessons"),
  get: (lessonId) => apiFetch(`/api/v1/lessons/${lessonId}`),
};

export const chat = {
  // language tells the backend which voice the frontend will ask for on the
  // follow-up voice.speak call, so it can warm that reply's TTS audio while
  // the LLM is still streaming it in (see ChatResponse.speech_id).
  start: ({ lesson_id, difficulty, mode, language }) =>
    apiFetch("/api/v1/chat/start", {
      method: "POST",
      body: { lesson_id, difficulty, mode, language },
    }),
  message: ({ lesson_id, difficulty, mode, language, messages }) =>
    apiFetch("/api/v1/chat/message", {
      method: "POST",
      body: { lesson_id, difficulty, mode, language, messages },
    }),
  getDraft: () => apiFetch("/api/v1/chat/draft"),
};

export const voice = {
  transcribe: async (audioBlob) => {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");
    return apiFetch("/api/v1/voice/transcribe", { method: "POST", formData });
  },
  // Returns the raw Response (not a Blob): the caller streams response.body
  // into playback as chunks arrive instead of waiting for the full download.
  // speechId, when the chat response carried one, lets the backend skip
  // resynthesizing audio it already started warming during LLM streaming.
  speak: (text, language, speechId) =>
    apiFetch("/api/v1/voice/speak", {
      method: "POST",
      body: { text, language, speech_id: speechId ?? null },
      raw: true,
    }),
};

export const sessions = {
  create: ({ lesson_id, messages, mistakes, mode }) =>
    apiFetch("/api/v1/sessions", { method: "POST", body: { lesson_id, messages, mistakes, mode } }),
  list: (limit = 10) => apiFetch(`/api/v1/sessions?limit=${limit}`).then((data) => data.sessions),
  get: (id) => apiFetch(`/api/v1/sessions/${id}`),
};

export const usage = {
  today: () => apiFetch("/api/v1/usage/today"),
};
