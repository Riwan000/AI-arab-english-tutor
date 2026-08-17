"""Browser voice recorder with automatic silence detection."""

from typing import Optional

from audio_recorder_streamlit import audio_recorder


# How long the user must remain silent before recording stops.
SILENCE_DURATION = 1.8


def record_voice() -> Optional[bytes]:
    """
    Record audio from the browser microphone.

    Recording automatically stops after the configured period of silence.

    Returns:
        Audio bytes when a recording is completed.
        None when the user has not recorded anything yet.
    """

    audio_bytes = audio_recorder(
        pause_threshold=SILENCE_DURATION,
        sample_rate=16000,
        energy_threshold=0.01,
        recording_color="#ea580c",
        neutral_color="#fdba74",
        icon_name="microphone",
        icon_size="2x",
        text="",
        start_prompt="🎤",
        stop_prompt="⏹️",
        show_visualizer=False,
    )

    return audio_bytes