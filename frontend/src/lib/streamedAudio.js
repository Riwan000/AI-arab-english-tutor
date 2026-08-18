// Plays a fetch Response's audio body into an <audio> element as the bytes
// arrive, instead of waiting for the whole clip to download first. Falls
// back to full-buffer playback (the old blob + object-URL flow) on browsers
// without MediaSource support for MP3 (e.g. older Safari).

const MSE_MIME_TYPE = "audio/mpeg";

function canStreamPlayback() {
  return (
    typeof MediaSource !== "undefined" &&
    MediaSource.isTypeSupported(MSE_MIME_TYPE)
  );
}

function waitForEvent(target, event) {
  return new Promise((resolve) => {
    const onEvent = () => {
      target.removeEventListener(event, onEvent);
      target.removeEventListener("error", onError);
      resolve();
    };
    const onError = onEvent;
    target.addEventListener(event, onEvent, { once: true });
    target.addEventListener("error", onError, { once: true });
  });
}

function appendChunk(sourceBuffer, chunk) {
  return new Promise((resolve, reject) => {
    const onUpdateEnd = () => {
      sourceBuffer.removeEventListener("updateend", onUpdateEnd);
      sourceBuffer.removeEventListener("error", onError);
      resolve();
    };
    const onError = () => {
      sourceBuffer.removeEventListener("updateend", onUpdateEnd);
      sourceBuffer.removeEventListener("error", onError);
      reject(new Error("SourceBuffer append failed"));
    };
    sourceBuffer.addEventListener("updateend", onUpdateEnd);
    sourceBuffer.addEventListener("error", onError);
    sourceBuffer.appendBuffer(chunk);
  });
}

// Starts playback and resolves once it naturally ends (or errors). If the
// browser blocks/rejects play() (e.g. no user-gesture in the call stack),
// resolves right away instead of waiting forever for an "ended" that will
// never fire.
async function playAndWaitForEnd(audioElement, onStart) {
  const ended = waitForEvent(audioElement, "ended");
  // Fire before awaiting play() so callers get exactly one "playback is
  // starting" signal even if the browser blocks/rejects autoplay.
  onStart?.();
  try {
    await audioElement.play();
  } catch (err) {
    console.warn("Autoplay blocked or audio play error:", err);
    return;
  }
  await ended;
}

// Firefox and older Chromium attach a MediaSource via a blob object URL.
// Recent Chrome dropped MediaSource support from URL.createObjectURL in
// favor of srcObject (the same mechanism used for MediaStream) and throws
// here instead. Only one of .src/.srcObject should ever be set on the
// element — setting both leaves it in a half-attached state where
// "sourceopen" never fires — so fall back inside the catch, not after
// mutating the element.
function attachMediaSource(audioElement, mediaSource) {
  try {
    const objectUrl = URL.createObjectURL(mediaSource);
    audioElement.src = objectUrl;
    return objectUrl;
  } catch {
    audioElement.srcObject = mediaSource;
    return null;
  }
}

async function streamIntoMediaSource(audioElement, response, signal, onStart) {
  const mediaSource = new MediaSource();
  const objectUrl = attachMediaSource(audioElement, mediaSource);

  try {
    await waitForEvent(mediaSource, "sourceopen");
    if (signal?.aborted) return;

    const sourceBuffer = mediaSource.addSourceBuffer(MSE_MIME_TYPE);
    const reader = response.body.getReader();
    signal?.addEventListener("abort", () => reader.cancel().catch(() => {}));

    let playback = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done || signal?.aborted) break;

      await appendChunk(sourceBuffer, value);

      if (!playback) {
        // Start playback as soon as the first chunk lands — don't wait for
        // the rest of the stream to finish appending.
        playback = playAndWaitForEnd(audioElement, onStart);
      }
    }

    if (mediaSource.readyState === "open" && !sourceBuffer.updating) {
      mediaSource.endOfStream();
    }

    if (!playback || signal?.aborted) return;
    await playback;
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}

async function playBuffered(audioElement, response, signal, onStart) {
  const blob = await response.blob();
  if (signal?.aborted) return;

  const url = URL.createObjectURL(blob);
  audioElement.src = url;

  try {
    await playAndWaitForEnd(audioElement, onStart);
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Plays a fetch Response's audio body through the given <audio> element,
 * starting playback as soon as the first chunk arrives when the browser
 * supports it. Resolves once playback ends (or is aborted/errors).
 *
 * @param {HTMLAudioElement} audioElement
 * @param {Response} response - a resolved fetch Response with a readable body
 * @param {{signal?: AbortSignal, onStart?: () => void}} [opts] - onStart fires
 *   once playback is attempted (whether or not it actually starts), so
 *   callers can sync other UI (e.g. revealing text) to when audio begins.
 */
export async function playStreamedAudio(audioElement, response, { signal, onStart } = {}) {
  if (canStreamPlayback() && response.body) {
    await streamIntoMediaSource(audioElement, response, signal, onStart);
  } else {
    await playBuffered(audioElement, response, signal, onStart);
  }
}
