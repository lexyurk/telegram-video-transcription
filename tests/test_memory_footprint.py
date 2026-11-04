"""Regression checks for optional imports and bounded SDK upload memory."""

import builtins
import importlib
import subprocess
import sys
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from deepgram import DeepgramClient

from telegram_bot.services import TranscriptionService

RESULTS = {
    "channels": [
        {
            "alternatives": [
                {
                    "transcript": "Hello there.",
                    "confidence": 0.99,
                    "paragraphs": {
                        "paragraphs": [
                            {
                                "speaker": 1,
                                "sentences": [
                                    {"text": "Hello there.", "start": 1.0, "end": 2.0}
                                ],
                            }
                        ]
                    },
                }
            ]
        }
    ],
}


class StreamingMockTransport(httpx.MockTransport):
    """Keep HTTPX's real encoding, but don't let MockTransport buffer the body.

    Standard MockTransport.handle_request calls request.read() before its handler.
    A socket transport consumes request.stream instead, so do that here too.
    """

    def handle_request(self, request):
        return self.handler(request)


class ReadGuard:
    """Reject unbounded reads while retaining file length/stream semantics."""

    def __init__(self, file):
        self.file = file
        self.open_thread = threading.get_ident()
        self.read_sizes = []
        self.close_thread = None

    def read(self, size=-1):
        assert 0 < size <= 65_536, f"Unbounded upload read: {size}"
        assert threading.get_ident() == self.open_thread
        self.read_sizes.append(size)
        return self.file.read(size)

    def __getattr__(self, name):
        return getattr(self.file, name)

    def __iter__(self):
        # File objects are iterable; HTTPX should use bounded read(), not lines.
        raise AssertionError("Upload must not iterate arbitrary-length lines")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close_thread = threading.get_ident()
        self.file.close()


@pytest.mark.parametrize("entrypoint", ["transcribe_audio", "transcribe_with_segments"])
@pytest.mark.parametrize(
    "outcome", ["success", "failure", "retry-status", "retry-network"]
)
@pytest.mark.asyncio
async def test_real_sdk_streams_upload_and_closes_file(
    tmp_path, monkeypatch, entrypoint, outcome
):
    """Exercise actual Deepgram -> HTTPX encoding, not a mocked SDK method."""
    media = tmp_path / "large.mp4"
    file_size = 64 * 1024 * 1024 + 17
    with media.open("wb") as output:
        output.write(b"replay-from-start")
        output.truncate(file_size)  # Sparse file, no large test fixture in memory.

    settings = SimpleNamespace(
        deepgram_model="nova-2",
        enable_smart_format=False,
        enable_punctuation=True,
        enable_paragraphs=True,
        enable_diarization=True,
        enable_filler_words=False,
        enable_profanity_filter=True,
    )
    monkeypatch.setattr(
        "telegram_bot.services.transcription_service.get_settings", lambda: settings
    )
    opened = []
    real_open = builtins.open

    def guarded_open(path, mode):
        assert path == str(media) and mode == "rb"
        wrapper = ReadGuard(real_open(path, mode))
        opened.append(wrapper)
        return wrapper

    monkeypatch.setattr(
        "telegram_bot.services.transcription_service.open", guarded_open, raising=False
    )
    requests = []
    monkeypatch.setattr("deepgram.core.http_client._retry_timeout", lambda **kwargs: 0)
    monkeypatch.setattr(
        "deepgram.core.http_client._retry_timeout_from_retries", lambda **kwargs: 0
    )

    def receive(request):
        assert opened and not opened[0].closed
        if not requests:
            assert not opened[0].read_sizes, "SDK buffered body before transport"
        with pytest.raises(httpx.RequestNotRead):
            _ = request.content
        assert request.headers["content-length"] == str(file_size)
        assert dict(request.url.params) == {
            "model": "nova-2",
            "detect_language": "true",
            "smart_format": "false",
            "punctuate": "true",
            "paragraphs": "true",
            "diarize": "true",
            "filler_words": "false",
            "profanity_filter": "true",
        }
        assert request.extensions["timeout"] == {
            "connect": 1234,
            "read": 1234,
            "write": 1234,
            "pool": 1234,
        }
        total = 0
        for chunk in request.stream:
            assert 0 < len(chunk) <= 65_536
            if total == 0:
                assert chunk.startswith(b"replay-from-start")
            total += len(chunk)
            if outcome == "failure":
                raise ValueError("Simulated transport upload failure")
        assert total == file_size
        requests.append(request)
        if len(requests) == 1:
            if outcome == "retry-status":
                return httpx.Response(503, json={"error": "retry this request"})
            if outcome == "retry-network":
                raise httpx.RemoteProtocolError("Simulated disconnect after upload")
        return httpx.Response(200, json={"results": RESULTS})

    main_thread = threading.get_ident()
    with httpx.Client(transport=StreamingMockTransport(receive)) as http_client:
        service = TranscriptionService.__new__(TranscriptionService)
        service.client = DeepgramClient(api_key="test-only", httpx_client=http_client)
        service.timeout_seconds = 1234
        result = await getattr(service, entrypoint)(str(media))

    if outcome == "failure":
        assert result == (None if entrypoint == "transcribe_audio" else (None, []))
    elif entrypoint == "transcribe_audio":
        assert result == "Speaker 1: Hello there."
    else:
        assert result == (
            "Speaker 1: Hello there.",
            [{"start": 1.0, "end": 2.0, "speaker": 1, "text": "Hello there."}],
        )
    assert len(opened) == 1
    assert opened[0].read_sizes
    assert opened[0].closed
    assert opened[0].open_thread != main_thread
    assert opened[0].close_thread == opened[0].open_thread
    assert len(requests) == (
        0 if outcome == "failure" else 2 if outcome.startswith("retry") else 1
    )


def test_core_import_and_diagram_init_skip_optional_heavy_stacks():
    """A fresh interpreter catches eager imports hidden by pytest's module cache."""
    code = """
import sys
from unittest.mock import MagicMock
from telegram_bot.services import (
    FileService, TranscriptionService, SummarizationService,
    SpeakerIdentificationService, DiagramService, QuestionAnsweringService,
    MediaInfoService, RAGStorageService,
)
diagram = DiagramService(ai_model=MagicMock())
assert diagram._python_generator is None
heavy = ('chromadb', 'onnxruntime', 'matplotlib', 'seaborn', 'scipy', 'pandas')
assert not [name for name in sys.modules if name.split('.')[0] in heavy]
"""
    subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )


def test_all_public_service_exports_remain_compatible():
    import telegram_bot.services as services

    for name, module_name in services._SERVICE_MODULES.items():
        assert name in services.__all__
        assert name in dir(services)
        expected = getattr(
            importlib.import_module(f"telegram_bot.services.{module_name}"), name
        )
        assert getattr(services, name) is expected
        assert getattr(services, name) is expected  # Cached identity.
    with pytest.raises(AttributeError):
        _ = services.not_a_service


@pytest.mark.asyncio
async def test_diagram_loads_generator_on_demand_and_creates_image(
    tmp_path, monkeypatch
):
    from telegram_bot.services import DiagramService
    from telegram_bot.services.python_diagram_generator import PythonDiagramGenerator

    monkeypatch.chdir(tmp_path)
    service = DiagramService(ai_model=MagicMock())
    assert service._python_generator is None
    service.data_extractor = SimpleNamespace(
        analyze_transcript_for_diagram_type=AsyncMock(return_value="chart"),
        extract_chart_data=AsyncMock(return_value=({"A": 2, "B": 3}, "bar")),
    )
    # Empty input should not load or construct the plotting generator.
    assert await service.create_diagram_from_transcript(" ") is None
    assert service._python_generator is None
    result = await service.create_diagram_from_transcript(
        "Speaker 1: A and B", "Counts"
    )
    assert isinstance(service.python_generator, PythonDiagramGenerator)
    assert service.python_generator is service.python_generator
    assert result is not None
    assert (tmp_path / result).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    service.data_extractor.extract_chart_data.assert_awaited_once_with(
        "A and B", "Counts"
    )


@pytest.mark.parametrize(
    "diagram_type,extractor,result,method",
    [
        (
            "flowchart",
            "extract_flowchart_data",
            ([{"id": "a"}], []),
            "create_flowchart",
        ),
        (
            "relationship",
            "extract_relationship_data",
            (["a"], []),
            "create_relationship_diagram",
        ),
        ("timeline", "extract_timeline_data", ["a"], "create_timeline_diagram"),
        ("hierarchy", "extract_hierarchy_data", {"a": []}, "create_hierarchy_diagram"),
        ("other", "extract_flowchart_data", ([{"id": "a"}], []), "create_flowchart"),
    ],
)
@pytest.mark.asyncio
async def test_diagram_routes_preserved(diagram_type, extractor, result, method):
    from telegram_bot.services import DiagramService

    service = DiagramService(ai_model=MagicMock())
    service.data_extractor = SimpleNamespace(
        analyze_transcript_for_diagram_type=AsyncMock(return_value=diagram_type),
        **{extractor: AsyncMock(return_value=result)},
    )
    generator = SimpleNamespace(**{method: AsyncMock(return_value="diagram.png")})
    service.python_generator = generator  # Existing injection remains supported.
    assert (
        await service.create_diagram_from_transcript("Speaker 1: Architecture")
        == "diagram.png"
    )
    getattr(service.data_extractor, extractor).assert_awaited_once_with(
        "Architecture", None
    )
    getattr(generator, method).assert_awaited_once()


@pytest.mark.parametrize("entrypoint", ["transcribe_audio", "transcribe_with_segments"])
@pytest.mark.asyncio
async def test_cancelling_async_caller_keeps_file_open_until_worker_finishes(
    tmp_path, monkeypatch, entrypoint
):
    import asyncio

    media = tmp_path / "audio.bin"
    media.write_bytes(b"audio")
    started, release, closed = threading.Event(), threading.Event(), threading.Event()
    opened = []
    real_open = builtins.open

    class ClosingGuard(ReadGuard):
        def __exit__(self, *args):
            super().__exit__(*args)
            closed.set()

    def guarded_open(path, mode):
        file = ClosingGuard(real_open(path, mode))
        opened.append(file)
        return file

    def upload(**kwargs):
        assert not opened[0].closed
        started.set()
        assert release.wait(timeout=5), "Test did not release upload worker"
        assert not opened[0].closed
        return {"results": RESULTS}

    settings = SimpleNamespace(
        deepgram_model="nova-2",
        enable_smart_format=True,
        enable_punctuation=True,
        enable_paragraphs=True,
        enable_diarization=True,
        enable_filler_words=True,
        enable_profanity_filter=False,
    )
    monkeypatch.setattr(
        "telegram_bot.services.transcription_service.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "telegram_bot.services.transcription_service.open", guarded_open, raising=False
    )
    service = TranscriptionService.__new__(TranscriptionService)
    service.client = SimpleNamespace(
        listen=SimpleNamespace(
            v1=SimpleNamespace(media=SimpleNamespace(transcribe_file=upload))
        )
    )
    service.timeout_seconds = 3600
    task = asyncio.create_task(getattr(service, entrypoint)(str(media)))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not opened[0].closed
    finally:
        release.set()
    assert await asyncio.to_thread(closed.wait, 2)
    assert opened[0].closed
    assert opened[0].open_thread == opened[0].close_thread
