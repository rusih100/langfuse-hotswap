# Security

Anyone who can edit a prompt in Langfuse controls its config. The library keeps that from becoming
control over credentials, endpoints or cost: the models are built in the code, and the config
changes only what `allowed_config_keys` permits (see [Models and config keys](models.md)).

**Start with the default.** With `allowed_config_keys=None` a prompt edit can switch between the
models the code built and nothing else.

**Allow sampling parameters, not infrastructure.** `{"model", "temperature", "max_tokens"}` is a
typical set. Values are checked only by the model constructor, so every allowed key is a parameter
the editors of the prompt control: `max_tokens` and a reasoning budget set the cost of a call.
`template_format` in the set lets them switch to `jinja2`, whose sandbox LangChain treats as best
effort against untrusted templates.

**Reserve `"any"` for trusted editors.** Every config key reaches the model constructor,
`base_url`, `api_key`, headers and `model_kwargs` included. For providers that rebuild their HTTP
client, a prompt edit can then send the requests, with the API key in the header, to another host.

**Guard the label.** The last guard is in Langfuse itself: use a dedicated label for production
and restrict who can move it. Build errors are logged with the exception text, which may include
config values.
