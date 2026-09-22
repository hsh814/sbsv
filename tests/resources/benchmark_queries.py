"""Run from the repository root: python -m tests.resources.benchmark_queries."""

import argparse
from timeit import repeat

import sbsv


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--rows", type=int, default=20000)
    args.add_argument("--repeat", type=int, default=5)
    args.add_argument("--python", action="store_true", help="disable native parsing")
    options = args.parse_args()
    if options.rows < 1 or options.repeat < 1:
        args.error("--rows and --repeat must be positive")

    parser = sbsv.parser(use_native=not options.python)
    parser.add_schema("[node] [value: int]")
    parser.add_schema("[edge] [value: int]")
    parser.loads(
        "".join(
            "[{}] [value {}]\n".format("node" if i % 2 else "edge", i)
            for i in range(options.rows)
        )
    )
    middle = options.rows // 2
    queries = [
        ("one schema", lambda: parser.get_result_in_order(["node"])),
        ("two schemas", lambda: parser.get_result_in_order(["node", "edge"])),
        ("range", lambda: parser.get_result_by_index("node", (middle, middle + 20))),
    ]
    for label, query in queries:
        elapsed = min(repeat(query, number=100, repeat=options.repeat)) / 100
        print("{}: {:.2f} us/query".format(label, elapsed * 1e6))

    wide_parser = sbsv.parser(use_native=not options.python)
    wide_parser.add_schema(
        "[wide] " + " ".join("[v{}: int]".format(i) for i in range(20))
    )
    line = "[wide] " + " ".join("[v{} {}]".format(i, i) for i in range(20)) + "\n"
    content = line * options.rows
    wide_parser.loads(line)  # Compile schemas before timing parser reuse.
    elapsed = min(
        repeat(lambda: wide_parser.loads(content), number=1, repeat=options.repeat)
    )
    backend = (
        "native" if wide_parser.use_native and sbsv.native_available() else "python"
    )
    print(
        "{} parsing: {:.0f} rows/s (20 fields/row)".format(
            backend, options.rows / elapsed
        )
    )


if __name__ == "__main__":
    main()
