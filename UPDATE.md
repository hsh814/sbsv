## v0.2.1
Major parser refactor and documentation update.

### Added
- `body_parser` for parsing schema bodies without a schema name.
- `parser.parse_line_detached()` for stateless single-line parsing.
- `ignore_prefix()` for skipping fixed prefixes, with optional `save_ignored=True` to keep ignored fields.
- Stricter custom type handling.
- Quoted string parsing and more flexible unquoted string handling.

### Changed
- Schema names, field names, and sub-schema names are validated more strictly.
- Schema types are validated when `add_schema()` is called.
- Escape and unescape behavior was updated to match the new string parsing rules.
- Error messages now include more context, including the input line when available.

### Breaking Changes
- `ignore_prefix()` and `add_custom_type()` must be called before adding any schema.
- Unknown schema types, including unknown list subtypes, now raise `ValueError` during schema registration.
- The first body field of a full-line schema cannot be nullable.
- Custom types are local to each parser instance.
- `ignore_prefix()` cannot be added after schemas exist.

## v0.1.x
Implement core parts of `sbsv`