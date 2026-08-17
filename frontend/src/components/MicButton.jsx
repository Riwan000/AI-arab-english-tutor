import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { voice } from "../api/client";

// Silence-based auto-stop:
// INITIAL_SILENCE_MS gives the learner time to begin speaking when auto-armed.
// POST_SPEECH_SILENCE_MS stops recording quickly after the user finishes speaking.
const SILENCE_THRESHOLD = 0.02;
const INITIAL_SILENCE_MS = 4000;
const POST_SPEECH_SILENCE_MS = 1800;

const MicButton = forwardRef(function MicButton({ t, onTranscribed, disabled }, ref) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const rafRef = useRef(null);
  const hasSpokenRef = useRef(false);

  useImperativeHandle(ref, () => ({
    startRecording: () => {
      if (!recording && !busy && !disabled) {
        startRecording();
      }
    },
    stopRecording: () => {
      if (recording) {
        stopRecording();
      }
    },
    isRecording: () => recording,
  }));

  function cleanupAudioAnalysis() {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
  }

  function watchForSilence(stream, onSilence) {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) return;
    const audioCtx = new AudioContextCtor();
    audioCtxRef.current = audioCtx;
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    hasSpokenRef.current = false;

    function tick() {
      analyser.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (let i = 0; i < data.length; i++) {
        const normalized = (data[i] - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / data.length);

      if (rms >= SILENCE_THRESHOLD) {
        hasSpokenRef.current = true;
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
      } else {
        const timeoutMs = hasSpokenRef.current ? POST_SPEECH_SILENCE_MS : INITIAL_SILENCE_MS;
        if (!silenceTimerRef.current) {
          silenceTimerRef.current = setTimeout(onSilence, timeoutMs);
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    }
    tick();
  }

  async function startRecording() {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = handleRecordingStop;

      recorder.start();
      setRecording(true);
      watchForSilence(stream, stopRecording);
    } catch {
      // Mic permission denied or unavailable — nothing to transcribe.
    }
  }

  function stopRecording() {
    cleanupAudioAnalysis();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setRecording(false);
  }

  async function handleRecordingStop() {
    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    chunksRef.current = [];
    if (blob.size === 0) return;

    setBusy(true);
    try {
      const result = await voice.transcribe(blob);
      if (result.text) onTranscribed(result.text);
    } catch {
      // Transcription failed — silently drop, learner can just retry.
    } finally {
      setBusy(false);
    }
  }

  function handleClick() {
    if (recording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  return (
    <button
      type="button"
      className={`mic-btn ${recording ? "recording" : ""}`}
      onClick={handleClick}
      disabled={disabled || busy}
      title={recording ? t("listening_label") : t("voice_input_label")}
      aria-label={recording ? t("listening_label") : t("voice_input_label")}
    >
      {recording ? "⏹" : "🎙️"}
    </button>
  );
});

export default MicButton;

