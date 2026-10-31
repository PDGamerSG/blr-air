"""Short local WAV recordings and spoken replies through Sarvam's REST APIs."""

import base64
import binascii
import io
import json
import os
import stat
import tempfile
import wave
from pathlib import Path

import httpx

from blr_air.domain import AirError

API_URL = "https://api.sarvam.ai"
MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_RESPONSE_BYTES = 48 * 1024 * 1024
STT_LANGUAGES = {
    "unknown",
    "hi-IN",
    "bn-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "od-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
    "en-IN",
    "gu-IN",
    "as-IN",
    "ur-IN",
    "ne-IN",
    "kok-IN",
    "ks-IN",
    "sd-IN",
    "sa-IN",
    "sat-IN",
    "mni-IN",
    "brx-IN",
    "mai-IN",
    "doi-IN",
}
TTS_SPEAKERS = {
    "en-IN": "simran_en_customer",
    "hi-IN": "aayan_hi_conversational",
    "bn-IN": "arnab_bn_conversation",
    "gu-IN": "bhavik_gu_conversation",
    "kn-IN": "chaitra_kn_conversation",
    "mr-IN": "ishita_mr_conversational",
    "pa-IN": "anand_pa_conversation",
    "ta-IN": "gokul_ta_narration",
    "te-IN": "kavitha_te_conversation",
}


def validate_wav(data: bytes, *, max_seconds: float | None = None):
    """Check the decoded container and frames, rather than trusting a file extension."""
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            frames, rate = audio.getnframes(), audio.getframerate()
            if (
                audio.getcomptype() != "NONE"
                or audio.getsampwidth() != 2
                or audio.getnchannels() not in (1, 2)
                or not 8000 <= rate <= 48000
                or frames <= 0
            ):
                raise ValueError("Unsupported PCM format")
            if max_seconds is not None and frames / rate > max_seconds:
                raise AirError("Voice input must be no longer than 30 seconds.")
            expected = frames * audio.getnchannels() * audio.getsampwidth()
            if len(audio.readframes(frames)) != expected:
                raise ValueError("Truncated WAV data")
    except (wave.Error, EOFError, OSError, ValueError) as exc:
        raise AirError(
            "Audio must be a complete, nonempty 16-bit PCM WAV, mono or stereo, at 8–48 kHz."
        ) from exc


class SarvamVoice:
    def __init__(self, client: httpx.AsyncClient, api_key: str):
        if not api_key or not api_key.strip():
            raise AirError("Voice requires SARVAM_API_KEY in your private .env file.")
        self.client = client
        self.api_key = api_key.strip()

    async def _request(self, endpoint: str, *, max_bytes: int, **kwargs) -> dict:
        try:
            async with self.client.stream(
                "POST",
                f"{API_URL}/{endpoint}",
                headers={"api-subscription-key": self.api_key},
                timeout=httpx.Timeout(60, connect=10),
                follow_redirects=False,
                **kwargs,
            ) as response:
                if response.status_code in (401, 403):
                    raise AirError("Sarvam rejected the API key. Check SARVAM_API_KEY and access.")
                if response.status_code == 429:
                    raise AirError("Sarvam is rate-limited or out of credits. Try again later.")
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > max_bytes:
                        raise AirError("Sarvam returned an unexpectedly large voice response.")
                    body.extend(chunk)
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Expected response object")
            return payload
        except httpx.TimeoutException:
            raise AirError("Sarvam voice request timed out. Please try again.") from None
        except httpx.HTTPStatusError as exc:
            raise AirError(
                f"Sarvam voice request failed (HTTP {exc.response.status_code}). "
                "Check your input or try again later."
            ) from None
        except httpx.RequestError:
            raise AirError("Could not reach Sarvam. Check your connection and try again.") from None
        except (ValueError, UnicodeDecodeError):
            raise AirError("Sarvam returned an invalid voice response. Please try again.") from None

    async def transcribe(self, path: Path, language: str = "unknown") -> str:
        """Return original-language text from a local WAV of at most 30 seconds."""
        if language not in STT_LANGUAGES:
            raise AirError("Unsupported speech input language. Use a BCP-47 code or unknown.")
        if path.suffix.lower() != ".wav":
            raise AirError("Voice input must be a local .wav file.")
        try:
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                raise AirError("Voice input must be a local regular .wav file.")
            if info.st_size > MAX_INPUT_BYTES:
                raise AirError("Voice input must be at most 10 MiB.")
            with path.open("rb") as handle:
                data = handle.read(MAX_INPUT_BYTES + 1)
            if len(data) > MAX_INPUT_BYTES:
                raise AirError("Voice input must be at most 10 MiB.")
        except OSError:
            raise AirError(
                "Could not read the local WAV file. Check its path and permissions."
            ) from None
        validate_wav(data, max_seconds=30)
        payload = await self._request(
            "speech-to-text",
            max_bytes=1024 * 1024,
            data={"model": "saaras:v4", "mode": "transcribe", "language_code": language},
            files={"file": (path.name, data, "audio/wav")},
        )
        transcript = payload.get("transcript")
        if not isinstance(transcript, str) or not transcript.strip():
            raise AirError(
                "No speech was recognized. Try a clearer recording or type your request."
            )
        return transcript.strip()

    async def synthesize(self, text: str, output: Path, language: str = "en-IN") -> Path:
        """Save speech to a new WAV; the supplied text must already be in the target language."""
        if not isinstance(text, str) or not text.strip() or len(text) > 2500:
            raise AirError("Spoken replies require between 1 and 2,500 characters of text.")
        if language not in TTS_SPEAKERS:
            raise AirError("Unsupported Bulbul v4 speech output language.")
        if output.suffix.lower() != ".wav":
            raise AirError("Speech output must use a .wav filename.")
        if output.exists() or output.is_symlink():
            raise AirError("Speech output already exists. Choose a new .wav filename.")
        if not output.parent.is_dir():
            raise AirError("The speech output directory does not exist.")
        payload = await self._request(
            "text-to-speech",
            max_bytes=MAX_RESPONSE_BYTES,
            json={
                "text": text,
                "language_code": language,
                "model": "bulbul:v4-flash",
                "speaker": TTS_SPEAKERS[language],
                "speech_sample_rate": 24000,
                "output_audio_codec": "wav",
            },
        )
        audios = payload.get("audios")
        if not isinstance(audios, list) or len(audios) != 1 or not isinstance(audios[0], str):
            raise AirError("Sarvam returned an invalid speech recording. Please try again.")
        try:
            data = base64.b64decode(audios[0], validate=True)
        except (ValueError, binascii.Error):
            raise AirError("Sarvam returned invalid audio encoding. Please try again.") from None
        validate_wav(data)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=output.parent, prefix=".blr-voice-", delete=False
            ) as f:
                temporary = Path(f.name)
                f.write(data)
            # Link publishes the complete file atomically and refuses existing files or symlinks.
            os.link(temporary, output)
        except OSError:
            raise AirError(
                "Could not save speech. Check permissions and choose an unused .wav filename."
            ) from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return output
