# Templates

Messages are rendered with the Langfuse substitution rules, so the result matches the playground.
The renderer is a copy of the SDK `TemplateParser`, and a contract test checks that both produce
the same text.

- A variable is whatever stands between `{{` and the next `}}`, stripped. Values are inserted with
  `str()` without escaping and `None` becomes an empty string.
- Every variable is required. Unlike `prompt.compile()`, a missing variable is an error, not left
  as is. The check is the LangChain prompt template one, so the error is a `KeyError` that names
  the missing variables.
- Single braces and HTML are left as they are. There are no mustache sections: `{{#flag}}` is a
  variable named `#flag`.
- Placeholders are filled from the input variable of the same name, which must be a list of
  messages. Variables inside those messages are not rendered.
- A text prompt becomes one `human` message. Roles LangChain does not know, such as `developer`,
  are kept as `ChatMessage` with that role.
- Variables named `stop` and `self` are rejected by LangChain.
