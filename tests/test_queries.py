import pytest

import sbsv


@pytest.fixture(params=[False, True], ids=["python", "native"])
def parsed(request):
    if request.param and not sbsv.native_available():
        pytest.skip("native extension is unavailable")
    parser = sbsv.parser(use_native=request.param)
    parser.add_schema("[graph] [node] [value: int]")
    parser.add_schema("[graph] [edge] [value: int]")
    parser.add_schema("[empty] [value: int]")
    parser.loads(
        "".join(
            "[graph] [{}] [value {}]\n".format("node" if i % 3 == 1 else "edge", i)
            for i in range(40)
        )
    )
    return parser


@pytest.mark.parametrize(
    "schemas, names",
    [
        ([], []),
        (["empty"], []),
        (["[graph] [node]"], ["graph$node"]),
        (["graph$edge", "empty", "graph$node"], ["graph$edge", "graph$node"]),
        (["graph$node", "[graph] [node]"], ["graph$node", "graph$node"]),
    ],
)
def test_ordered_queries_preserve_order_and_row_identity(parsed, schemas, names):
    expected = [row for row in parsed.data for name in names if row.schema_name == name]
    actual = parsed.get_result_in_order(schemas)
    assert [row.id for row in actual] == [row.id for row in expected]
    assert all(a is b for a, b in zip(actual, expected))
    actual.clear()
    assert len(parsed.data) == 40
    assert len(parsed.schema["graph$node"].data) == 13


def test_range_queries_include_boundaries_and_handle_empty_ranges(parsed):
    for schema in ("[graph] [node]", "graph$edge", "empty"):
        rows = parsed.get_result_in_order([schema])
        for start in range(-1, 43):
            for end in range(-1, 43):
                expected = [row for row in rows if start <= row.id <= end]
                actual = parsed.get_result_by_index(schema, (start, end))
                assert [row.id for row in actual] == [row.id for row in expected]
                assert all(a is b for a, b in zip(actual, expected))


def test_query_validation_and_unfiltered_result(parsed):
    assert parsed.get_result_in_order() is parsed.data
    with pytest.raises(ValueError, match="Invalid schema missing"):
        parsed.get_result_in_order(["graph$node", "missing"])
    with pytest.raises(ValueError, match="Invalid schema missing"):
        parsed.get_result_by_index("missing", (0, 10))


@pytest.mark.parametrize("use_native", [False, True])
def test_body_tokens_after_first_value_are_not_schema_names(use_native):
    parser = sbsv.parser(use_native=use_native)
    parser.add_schema("[graph] [node] [value: int] [label: str] [optional?: str]")
    row = parser.loads(
        '[graph] [node] [value 1] [extra] [label "[nested]"] [optional]'
    )["graph"]["node"][0]
    assert row.data == {"value": 1, "label": "[nested]", "optional": None}
