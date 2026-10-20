---
paths:
  - "tests/**/*.py"
---

# Tests

- One test module per source module: `test_factory.py`, `test_prompts.py`, `test_runnable.py`,
  `test_template.py`. Inside a module, group tests under `# Section` comments.
- `test_sdk_contract.py` pins the Langfuse SDK behavior the library relies on. It is the one
  module that uses a real `Langfuse` client (tracing disabled, unreachable host, `api.prompts`
  stubbed) and may import SDK internals. A new assumption about the SDK gets a test there.
- Every test has a docstring with one sentence that states the behavior under test, in the
  present tense: "A version that fails to build is served by the previous chain and logged once."
  Not "Tests that…", not the implementation.
- The test name and the docstring describe the same behavior; rename the test when it changes.
- Arrange, act and assert are separated by blank lines.
- Use the fixtures from `conftest.py`: `client` (fake Langfuse), `factory` (one `FakeChatModel`
  named `fake`, `allowed_config_keys="any"`), `builds` (records the prompt of every model build).
- Shared doubles live in `fakes.py`. `FakeChatModel` mirrors `ChatOpenAI` in storing the model
  name as `model_name` behind the alias `model`. Do not add network calls or real providers.
- A broken prompt config in a test is a value the model constructor rejects, such as
  `{"temperature": "hot"}`.
- Concurrency tests may slow a hook down with a short `time.sleep` so that concurrent calls
  overlap. Use `threading.Event` with a timeout when the test needs an exact interleaving.
- A security rule (the default `None`, the allowlist, `provider` selection) gets a test that tries
  to break it.
