## v0.3.1

### Changed
- Tokenize into one packed pointer-and-byte allocation with a direct ordinary-line
  scan instead of per-character growth and one allocation per token.
- Reject unknown root schemas before tokenization when `ignore_unknown` is enabled.
- Construct native `SbsvData` rows directly and cache interned schema/field names.

### Fixed
- Make `clone()` configuration and result state independent.
- Clear parser rows before schemas during destruction, preventing field-name
  use-after-free.
- Preserve parsing of SBSV rows preceded by timestamps or other unbracketed text.

### Breaking changes
- `load()` and `loads()` replace prior rows and group state instead of accumulating
  results from earlier calls. Use incremental `parse_line()` when appending is intended.
- `SbsvData` is now a `dict` subclass; `.data` remains an alias to the same mapping.
- The C `sbsv_token_list` layout now includes its packed-allocation owner. Recompile
  consumers and release token lists only through `sbsv_free_token_list()`.

## v0.3.0

### Added
- `libsbsv` integration for faster parsing.
- Built-in `hex` and `list[hex]` conversion in Python and `libsbsv`, including
  unsigned 64-bit and arbitrary-precision values without Python callbacks.
- Native parsing for schemas that contain Python custom types; callbacks run
  only for fields declared with those types.

### Changed
- Reuse compiled native schemas across bulk and detached-line parsing.
- Defer Python custom conversion until structural native parsing succeeds.
- Avoid a second native pass when bulk parsing falls back to Python.
- Reduce pure-Python fallback scanning and avoid materializing every input line.

### Breaking changes
- Now hex is a built-in type with support for unsigned 64-bit and arbitrary-precision values.
- You cannot add custom types with the same name as built-in types: hex will raise a `ValueError`.


## v0.2.3

### Added
- Optional CPython acceleration backed by `libsbsv`, with automatic pure Python fallback.
- `parser(use_native=False)` to force the reference Python implementation.
- `sbsv.native_available()` for runtime backend detection.
- Arbitrary-precision integer preservation in `libsbsv` through `SBSV_VALUE_BIG_INT`.

### Changed
- Reduced native token copies and per-field allocations.
- Added fast paths for unescaped Python strings and cached type information.
- Replaced the synchronized ordering queue with `heapq`.

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
