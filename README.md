# SBSV: square bracket separated values
A flexible, schema-based structured log data format.

## Install

```shell
python3 -m pip install sbsv
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
- [ ] Not available yet
```
[2024-03-04 13:22:56] [DEBUG] [necessary] [from] [this part]
```
Regular log file may contain unnecessary data. You can specify parser to ignore `[2024-03-04 13:22:56] [DEBUG]` part.

```python
parser.add_schema("[$ignore] [$ignore] [necessary] [from] [this: str]")
```

### Duplicating names
Sometimes, you may want to use same name multiple times. You can distinguish them using additional tags.
```
[my-schema] [node 1] [node 2] [node 3]
```
Tag is added like `node$some-tag`, after `$`. Data should not contain tags: they will be only used in schema.
```python
parser.add_schema("[my-schema] [node$0: int] [node$1: int] [node$2: int]")
result = parser.loads("[my-schema] [node 1] [node 2] [node 3]\n")
result["my-schema"][0]["node$0"] == 1
```

### Name matching
If there are additional element in data, it will be ignored.
The sequence of the names should not be changed.
```python
parser.add_schema("[my-schema] [node: int] [value: int]")
data = "[my-schema] [node 1] [unknown element] [value 3]\n"
result = parser.loads(data)
result["my-schema"][0] == { "node": 1, "value": 3 }
```

### Ordering
You may need a global ordering of each line.
```python
parser.add_schema("[data] [string] [id: int] [actual: str]")
parser.add_schema("[data] [token] [id: int] [actual: list[str]]")
result = parser.load(f)
# This returns all elements in order
elems_all = parser.get_result_in_order()
# This returns elements matching names in order
# If it contains sub-schema, use $
# For example, [data] [string] [id: int] -> "data$string"
elems = parser.get_result_in_order(["data$string", "data$token"])
```

### Primitive types
Primitive types are `str`, `int`, `float`, `bool`, `null`.

### Complex types

#### nullable
```
[car] [id 1] [speed 100] [power 2] [price]
[car] [id] [speed 120] [power 3] [price 33000]
```

```python
parser.add_schema("[car] [id?: int] [data: obj[speed: int, power: int, price?: int]]")
```

- [ ] Not available yet
#### list
```
[data] [token] [id 2] [actual [some] [multiple] [tokens]]
```

```python
parser.add_schema("[data] [token] [id: int] [actual: list[str]]")
```

#### obj
```
[car] [id 1] [data [speed 100] [power 2] [price 20000]]
```
```python
parser.add_schema("[car] [id: int] [data: obj[speed: int, power: int, price: int]])
```

#### map
```
[map-example] [mymap [id: 1, name: alice, email: wd@email.com]]
```
```python
parser.add_schema("[map-example] [mymap: map]")
```


### Escape sequences for string
```
[car] [id 1] [name "\[name with square bracket\]"]
```

## Contribute
```shell
python3 -m pip install --upgrade pip
python3 -m pip install black
```
You should run `black` linter before commit.
```shell
python3 -m black .
```

Before implementing new features or fixing bugs, add new tests in `tests/`.
```shell
python3 -m unittest
```

Build and update
```shell
python3 -m build
python3 -m twine upload dist/*
```