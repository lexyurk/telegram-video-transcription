# Transcription memory footprint

## What changed

- Public service exports resolve lazily. Importing core bot services no longer
  imports unused ChromaDB/ONNX or the plotting stack through `services/__init__.py`.
  Explicit imports of RAG services still load their dependencies and work as before.
- `DiagramService` retains its public `python_generator` attribute via a lazy
  property. The first actual diagram request loads the generator, not bot startup.
  Diagram generation can therefore still increase memory later in the process.
- Both transcription entrypoints send the binary file stream, instead of reading
  the entire audio/video file into a `bytes` object first. Size-based timeouts use
  `stat()`. Open, synchronous upload, and close all belong to the worker thread,
  including when its async caller is cancelled.

These are separate sources of memory pressure. They do not prove that any
particular portion of the observed production container's roughly 795 MiB was
caused by one import or upload. Production RSS includes additional state, native
allocations, allocator retention, and potentially prior requests.

## Reproduce cold-import measurements

Use the **same dependency environment and Python executable** for each checkout.
For the locked environment (Python 3.12 avoids the pinned NumPy version's missing
3.13 wheel):

```sh
uv sync --frozen --extra dev --no-install-project --python 3.12
# Match the measured live dependency versions in the local env only:
uv pip install 'deepgram-sdk==7.1.1' 'httpx==0.28.1' 'chromadb==1.5.9' 'matplotlib==3.10.9' 'seaborn==0.13.2'
.venv/bin/python scripts/measure_import_memory.py
```

To reproduce against the baseline, make a separate checkout of `ca2af4c`, copy
only the measurement script there, then run it with the absolute path to the same
virtualenv Python while your working directory is that checkout. Run three fresh
processes per revision; compare medians, retaining individual values because
first-run font caches can affect import cost. The script imports `telegram_bot.bot`
without creating the bot, contacting providers, or reading credentials.

Observed local comparison on 2026-11-03, macOS/Python 3.12.12, with server-matched
Deepgram SDK 7.1.1, HTTPX 0.28.1, ChromaDB 1.5.9, Matplotlib 3.10.9, and Seaborn
0.13.2 (other dependencies from `uv.lock`):

- Baseline peak RSS MiB: 398.16, 255.33, 255.84; median **255.84**.
- Updated peak RSS MiB: 117.83, 114.95, 114.88; median **114.95**.
- Heavy module roots above were loaded before, absent after this core import.

This is a cold-import experiment, **not** production container RSS or an expected
server reduction. The live runtime uses Linux/Python 3.11. Repeat production
measurements on the same runtime, request history, and representative media before
claiming server savings. Record container `docker stats --no-stream` and process
RSS before/after restart, idle startup, transcription, and an optional diagram;
allow equal settling periods. Keep private media and provider credentials local.

## Upload verification

```sh
.venv/bin/python -m pytest tests/test_memory_footprint.py -q
```

The tests use the real SDK and HTTPX request encoder with a 64 MiB sparse input,
reject unbounded source reads, and assert at the transport boundary that the body
is not already buffered. Deepgram SDK 7.1.1's media raw client passes
`content=request` to HTTPX; HTTPX 0.28.1's `IteratorByteStream` consumes the
replayable upload iterable, which seeks to the file's start on each HTTP request
and yields 65,536-byte chunks. This preserves whole-file replay on SDK retries
while retaining Content-Length through the file descriptor. The test's `StreamingMockTransport` intentionally
bypasses standard `MockTransport.handle_request`'s eager `request.read()` so the
transport consumes chunks like the real socket transport, without retaining them.
It checks both transcription entrypoints, request options/timeouts, returned text
and speaker segments, and descriptor closure after successful or failed uploads.
The same checks cover a 503 response and a transport disconnect after the first
complete upload; each SDK retry must resend the entire body from its first byte.
No live transcription/provider calls are made.

This bounds the upload body, not response data, concurrent request count, or
plotting/RAG allocations. The SDK's pre-existing retry behavior is unchanged;
this patch does not add a new retry policy.
