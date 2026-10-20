# Templates

`template_format` on the factory selects how the messages are rendered; its default, `langfuse`,
matches the playground. A prompt may carry its own format in the config key `template_format`,
which applies when `allowed_config_keys` names it or is `"any"` (see
[Models and config keys](models.md#allowed-config-keys)). The key never reaches the model.

```json
{"provider": "openai", "model": "gpt-5.5", "template_format": "jinja2"}
```

| Format | Syntax | Rendered by |
|---|---|---|
| `langfuse` (default) | `{{ name }}` | The `TemplateParser` of the Langfuse SDK |
| `f-string` | `{name}` | `str.format`, as in LangChain prompt templates |
| `mustache` | `{{ name }}`, `{{{ name }}}`, `{{#flag}}...{{/flag}}` | The LangChain mustache renderer |
| `jinja2` | `{{ name \| upper }}`, `{% if %}` | Jinja2 in a sandbox, as in LangChain; needs `pip install "langfuse-hotswap[jinja2]"` |

The format applies to every message of the prompt. In every format the variables are required:
the input is validated by the LangChain prompt template, so a missing variable raises a `KeyError`
that names it.

## The `langfuse` format

Messages are rendered by the `TemplateParser` of the Langfuse SDK, so the result matches the
playground. A contract test pins its rules:

- A variable is whatever stands between `{{` and the next `}}`, stripped. Values are inserted with
  `str()` without escaping and `None` becomes an empty string.
- Single braces and HTML are left as they are. There are no sections: `{{#flag}}` is a variable
  named `#flag`, and `{{a.b}}` is a variable named `a.b`.
- Unlike `prompt.compile()`, a missing variable is an error, not left as is.

## The LangChain formats

`f-string`, `mustache` and `jinja2` are rendered by the functions behind `ChatPromptTemplate`
with the same `template_format`, with their rules: `f-string` treats single braces as fields,
`mustache` escapes HTML in `{{ }}`, renders sections and treats `a.b` as a nested lookup, `jinja2`
evaluates expressions and filters. Use them for prompts that need conditions or loops, and keep in
mind that the Langfuse playground renders `{{ name }}` only.

## Messages

- A text prompt becomes one `human` message. Roles LangChain does not know, such as `developer`,
  are kept as `ChatMessage` with that role.
- Placeholders are filled from the input variable of the same name, which must be a list of
  messages. Variables inside those messages are not rendered.
- Variables named `stop` and `self` are rejected by LangChain.
