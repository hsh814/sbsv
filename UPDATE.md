## Unreleased

### Added
- Built-in `hex` and `list[hex]` conversion in Python and `libsbsv`, including
  unsigned 64-bit and arbitrary-precision values without Python callbacks.
- Native parsing for schemas that contain Python custom types; callbacks run
  only for fields declared with those types.

### Changed
- Reuse compiled native schemas across bulk and detached-line parsing.
- Defer Python custom conversion until structural native parsing succeeds.
- Avoid a second native pass when bulk parsing falls back to Python.
- Reduce pure-Python fallback scanning and avoid materializing every input line.

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
