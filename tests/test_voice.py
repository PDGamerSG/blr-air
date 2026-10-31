import base64
import io
import json
import wave
from email import policy
from email.parser import BytesParser

import httpx
import pytest

from blr_air.domain import AirError


def wav_bytes(*, seconds=0.1, sample_rate=16000, channels=1, width=2):
    data = io.BytesIO()
    with wave.open(data, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(width)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00" * int(seconds * sample_rate) * channels * width)
    return data.getvalue()


@pytest.fixture
def recording(tmp_path):
    path = tmp_path / "request.wav"
    path.write_bytes(wav_bytes())
    return path


async def test_transcribe_sends_real_wav_as_multipart_and_returns_trimmed_text(recording):
    from blr_air.voice import SarvamVoice

    def respond(request):
        assert str(request.url) == "https://api.sarvam.ai/speech-to-text"
        assert request.headers["api-subscription-key"] == "test-key"
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: "
            + request.headers["content-type"].encode()
            + b"\r\n\r\n"
            + request.content
        )
        fields = {
            part.get_param("name", header="content-disposition"): part.get_payload(decode=True)
            for part in message.iter_parts()
        }
        assert fields["file"] == recording.read_bytes()
        assert fields["model"] == b"saaras:v4"
        assert fields["mode"] == b"transcribe"
        assert fields["language_code"] == b"unknown"
        return httpx.Response(
            200,
            json={
                "request_id": "example",
                "transcript": "  run in HSR Layout tomorrow  ",
                "language_code": "en-IN",
                "language_probability": 0.95,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await SarvamVoice(client, "test-key").transcribe(recording) == (
            "run in HSR Layout tomorrow"
        )


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not a wave file",
        wav_bytes()[:-2],
        wav_bytes(seconds=0),
        wav_bytes(seconds=30.1),
        wav_bytes(width=1),
    ],
    ids=["empty", "wrong-format", "truncated", "zero-frames", "long", "8-bit"],
)
async def test_invalid_wav_is_rejected_before_upload(recording, data):
    from blr_air.voice import SarvamVoice

    recording.write_bytes(data)

    def offline(request):
        raise AssertionError("Invalid audio must not be uploaded")

    async with httpx.AsyncClient(transport=httpx.MockTransport(offline)) as client:
        with pytest.raises(AirError):
            await SarvamVoice(client, "test-key").transcribe(recording)


async def test_file_size_limit_is_checked_before_reading_or_upload(recording):
    from blr_air.voice import SarvamVoice

    with recording.open("wb") as handle:
        handle.truncate(11 * 1024 * 1024)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: pytest.fail())
    ) as client:
        with pytest.raises(AirError, match="10 MiB"):
            await SarvamVoice(client, "test-key").transcribe(recording)


@pytest.mark.parametrize("filename", ["request.mp3", "missing.wav", "."])
async def test_only_local_regular_wav_files_are_accepted(tmp_path, filename):
    from blr_air.voice import SarvamVoice

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: pytest.fail())
    ) as client:
        with pytest.raises(AirError):
            await SarvamVoice(client, "test-key").transcribe(tmp_path / filename)


@pytest.mark.parametrize("payload", [{}, {"transcript": None}, {"transcript": "  "}, []])
async def test_bad_transcript_fails_without_inventing_a_request(recording, payload):
    from blr_air.voice import SarvamVoice

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(AirError):
            await SarvamVoice(client, "test-key").transcribe(recording)


async def test_synthesize_requests_documented_voice_and_saves_valid_private_wav(tmp_path):
    from blr_air.voice import SarvamVoice

    audio = wav_bytes(sample_rate=24000)

    def respond(request):
        assert str(request.url) == "https://api.sarvam.ai/text-to-speech"
        assert request.headers["api-subscription-key"] == "test-key"
        assert json.loads(request.content) == {
            "text": "Run tomorrow at seven AM.",
            "language_code": "en-IN",
            "model": "bulbul:v4-flash",
            "speaker": "simran_en_customer",
            "speech_sample_rate": 24000,
            "output_audio_codec": "wav",
        }
        return httpx.Response(
            200,
            json={
                "request_id": "example",
                "audios": [base64.b64encode(audio).decode()],
            },
        )

    output = tmp_path / "answer.wav"
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert (
            await SarvamVoice(client, "test-key").synthesize("Run tomorrow at seven AM.", output)
            == output
        )
    assert output.read_bytes() == audio
    assert output.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize(
    "audios",
    [
        [],
        ["not base64!"],
        [base64.b64encode(b"not audio").decode()],
        [base64.b64encode(wav_bytes()[:-2]).decode()],
        ["a", "b"],
        "not an array",
    ],
    ids=["empty", "invalid-base64", "not-wav", "truncated", "many", "string"],
)
async def test_invalid_speech_response_never_creates_output(tmp_path, audios):
    from blr_air.voice import SarvamVoice

    output = tmp_path / "answer.wav"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"request_id": "example", "audios": audios})
        )
    ) as client:
        with pytest.raises(AirError):
            await SarvamVoice(client, "test-key").synthesize("Run tomorrow.", output)
    assert not output.exists()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("text", ["", "   ", "x" * 2501], ids=["empty", "blank", "long"])
async def test_tts_text_limit_fails_before_provider_call(tmp_path, text):
    from blr_air.voice import SarvamVoice

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: pytest.fail())
    ) as client:
        with pytest.raises(AirError):
            await SarvamVoice(client, "test-key").synthesize(text, tmp_path / "answer.wav")


@pytest.mark.parametrize("is_symlink", [False, True])
async def test_output_never_overwrites_existing_file_or_symlink(tmp_path, is_symlink):
    from blr_air.voice import SarvamVoice

    target = tmp_path / "original.wav"
    target.write_bytes(b"existing data")
    output = tmp_path / "answer.wav" if is_symlink else target
    if is_symlink:
        output.symlink_to(target)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: pytest.fail())
    ) as client:
        with pytest.raises(AirError):
            await SarvamVoice(client, "test-key").synthesize("Run tomorrow.", output)
    assert target.read_bytes() == b"existing data"


@pytest.mark.parametrize("status", [302, 401, 403, 422, 429, 503])
async def test_provider_errors_and_redirects_do_not_expose_secrets(recording, status):
    from blr_air.voice import SarvamVoice

    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            status,
            headers={"location": "https://untrusted.example/audio"},
            json={"error": {"message": "secret-test-key raw provider body"}},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), follow_redirects=True
    ) as client:
        with pytest.raises(AirError) as error:
            await SarvamVoice(client, "secret-test-key").transcribe(recording)
    assert "secret-test-key" not in str(error.value)
    assert "raw provider body" not in str(error.value)
    assert len(requests) == 1


async def test_network_timeout_is_actionable_air_error(recording):
    from blr_air.voice import SarvamVoice

    def timeout(request):
        raise httpx.ReadTimeout("secret-test-key", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(AirError, match="timed out") as error:
            await SarvamVoice(client, "secret-test-key").transcribe(recording)
    assert "secret-test-key" not in str(error.value)


async def test_empty_api_key_is_actionable(tmp_path):
    from blr_air.voice import SarvamVoice

    async with httpx.AsyncClient() as client:
        with pytest.raises(AirError, match="SARVAM_API_KEY"):
            SarvamVoice(client, " ")


async def test_output_created_during_request_is_preserved_and_temporary_file_cleaned(tmp_path):
    from blr_air.voice import SarvamVoice

    output = tmp_path / "answer.wav"

    def respond(request):
        output.write_bytes(b"created by another process")
        return httpx.Response(
            200,
            json={
                "request_id": "example",
                "audios": [base64.b64encode(wav_bytes()).decode()],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(AirError):
            await SarvamVoice(client, "test-key").synthesize("Run tomorrow.", output)
    assert output.read_bytes() == b"created by another process"
    assert list(tmp_path.iterdir()) == [output]


async def test_kannada_uses_matching_speaker_and_preserves_native_text(tmp_path):
    from blr_air.voice import SarvamVoice

    def respond(request):
        payload = json.loads(request.content)
        assert payload["language_code"] == "kn-IN"
        assert payload["speaker"] == "chaitra_kn_conversation"
        assert payload["text"] == "ನಾಳೆ ಬೆಳಿಗ್ಗೆ ಓಡಿ."
        return httpx.Response(
            200,
            json={
                "request_id": "example",
                "audios": [base64.b64encode(wav_bytes()).decode()],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await SarvamVoice(client, "test-key").synthesize(
            "ನಾಳೆ ಬೆಳಿಗ್ಗೆ ಓಡಿ.", tmp_path / "kannada.wav", language="kn-IN"
        )


async def test_malformed_provider_json_is_an_air_error(recording):
    from blr_air.voice import SarvamVoice

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"not JSON"))
    ) as client:
        with pytest.raises(AirError):
            await SarvamVoice(client, "test-key").transcribe(recording)
