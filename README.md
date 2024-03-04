# SBSV: square bracket separated values

## Install

```shell
python3 -m pip install svsb
```

## Use
You can read this log-like data:
```sbsv
[meta-data] [id 1] [format string]
[meta-data] [id 2] [format token]
[data] [string] [id 1] [actual some long string...]
[data] [token] [id 2] [actual [some] [multiple] [tokens]]
[stat] [rows 2]
```

```python
import sbsv

parser = sbsv.parser()
parser.add_schema("[meta-data] [id: int] [format: str]")
parser.add_schema("[data] [string] [id: int] [actual: str]")
parser.add_schema("[data] [token] [id: int] [actual: list[str]]")
parser.add_schema("[stat] [rows: int]")
with open("testfile.svsb", "r") as f:
  result = parser.load(f)
```

Result would looks like:
```
{
  "meta-data": [{"id": 1, "format": "string"}, {"id": 2, "format": "string"}],
  "data": {
    "string": [{"id": 1, "actual": "some long string..."}],
    "token": [{"id": 2, "actual": ["some", "multiple", "tokens"]}]
  },
  "stat": [{"rows": 2}]
}
```

## Details
### Basic schema
Schema is consisted with schema name, variable name and type annotation.
```
[schema-name] [var-name: type]
```
You can use [A-Za-z0-9\-_] for names. 

### Sub schema
```
[my-schema] [sub-schema] [some: int] [other: str] [data: bool]
```
You can add any sub schema.
But if you add sub schema, you cannot add new schema with same schema name without sub schema.
```
[my-schema] [no: int] [sub: str] [schema: str]
# this will cause error
```

### Ignore
```
[2024-03-04 13:22:56] [DEBUG] [necessary] [from] [this part]
```
Regular log file may contain unnecessary data. You can specify parser to ignore `[2024-03-04 13:22:56] [DEBUG]` part.

```python
parser.add_schema("[$ignore] [$ignore] [necessary] [from] [this: str]")
```

### Primitive types
Primitive types are `str`, `int`, `float`, `bool`, `null`.

### Complex types
You can use `list`.

