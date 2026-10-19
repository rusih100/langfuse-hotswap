---
paths:
  - "tests/**/*.py"
---

# Tests

- One test module per source module: `test_config.py`, `test_runnable.py`, `test_template.py`,
  `test_factory.py`. Inside a module, group tests under `# Section` comments.
- Every test has a docstring with one sentence that states the behavior under test, in the
  present tense: "A version that fails to build is served by the previous chain and logged once."
  Not "Tests that…", not the implementation.
- The test name and the docstring describe the same behavior; rename the test when it changes.
- Arrange, act and assert are separated by blank lines.
- Use the fixtures from `conftest.py`: `client` (fake Langfuse), `init_calls` (records the
  `init_chat_model` arguments and returns `FakeChatModel`), `factory` (allowlist disabled).
- Shared doubles live in `fakes.py`. Do not add network calls or real providers.
- Time-dependent behavior (the one-minute windows) is tested by patching
  `langfuse_hotswap._runnable.time.monotonic`, not by sleeping.
- Concurrency tests may slow a hook down with a short `time.sleep` so that concurrent calls
  overlap. Use `threading.Event` with a timeout when the test needs an exact interleaving.
- A security rule (blocked keys, provider selection, precedence) gets a test that tries to break it.
