import sbsv
import unittest
import os
import time
from typing import TextIO, Iterator, Dict, List, Optional

RESOURCE_DIR = os.path.dirname(__file__)


class SbsvLogParser:
    parser: sbsv.parser
    fp: TextIO
    rows_seen: int

    def __init__(self, fp: TextIO):
        # https://github.com/hsh814/sbsv
        self.parser = sbsv.parser()
        self.parser.add_schema("[alloc] [start] [base: hex] [size: hex] [pc: hex]")
        self.parser.add_schema("[calloc] [size: hex] [pc: hex]")
        self.parser.add_schema("[free] [done] [base: hex] [pc: hex]")
        self.parser.add_schema(
            "[stack] [push] [sp: hex] [size: hex] [pc: hex] [depth: int] [sr-base: hex] [sr-size: hex]"
        )
        self.parser.add_schema(
            "[stack] [pop] [sp: hex] [base: hex] [pc: hex] [depth: int]"
        )
        self.parser.add_schema("[global] [add] [base: hex] [size: hex] [name: str]")
        # loadh/storeh: val - successfully detect base address, val-fallback - fallback to register value, inval - failed to detect base address, only have access addr
        #  [r0: hex] [r1: hex] [r2: hex] [r3: hex] [r4: hex] [r5: hex] [r6: hex] [r7: hex] [r8: hex] [r9: hex] [r10: hex] [r11: hex] [r12: hex] [r13: hex] [r14: hex] [r15: hex]
        self.parser.add_schema(
            "[loadh] [val] [reg: str] [pc: hex] [addr: hex] [base: hex] [disp: int] [reg-base: hex] [size: hex] [val: hex] [is-ptr: bool]"
        )
        self.parser.add_schema(
            "[loadh] [val-fallback] [reg: str] [pc: hex] [addr: hex] [base: hex] [disp: int] [reg-base: hex] [size: hex] [val: hex] [is-ptr: bool] "
        )
        self.parser.add_schema(
            "[loadh] [inval] [reg: str] [pc: hex] [addr: hex] [reg-base: hex] [size: hex] [val: hex] [is-ptr: bool] "
        )
        self.parser.add_schema("[loadh-error] [pc: hex] [addr: hex] [size: hex]")
        self.parser.add_schema(
            "[storeh] [val] [reg: str] [pc: hex] [addr: hex] [base: hex] [disp: int] [reg-base: hex] [size: hex] [val: hex] [is-ptr: bool] "
        )
        self.parser.add_schema(
            "[storeh] [val-fallback] [reg: str] [pc: hex] [addr: hex] [base: hex] [disp: int] [reg-base: hex] [size: hex] [val: hex] [is-ptr: bool] "
        )
        self.parser.add_schema(
            "[storeh] [inval] [reg: str] [pc: hex] [addr: hex] [reg-base: hex] [size: hex] [val: hex] [is-ptr: bool] "
        )
        # memmoveh: this include register copy, memcpy, memmove, strcpy
        self.parser.add_schema(
            "[memmoveh] [src: hex] [dst: hex] [size: hex] [val: hex] [is-ptr: bool] [src-r: str] [src-rb: hex] [dst-r: str] [dst-rb: hex] "
        )
        # cov: edge coverage
        # self.parser.add_schema("[cov] [base] [from: hex] [to: hex] [cnt: int]")
        # self.parser.add_schema("[cov] [update] [from: hex] [to: hex] [cnt: int]")
        # Read access for pointer
        # self.parser.add_schema("[rpo] [addr: hex] [target: hex] [pc: hex] [index: int] [id: int]")
        self.fp = fp
        self.rows_seen = 0

    def get_result_in_order(self) -> Iterator[sbsv.SbsvData]:
        line_num = 0
        for line in self.fp:
            line_num += 1
            self.rows_seen += 1
            if not line.startswith(
                (
                    "[alloc]",
                    "[calloc]",
                    "[free]",
                    "[stack]",
                    "[global]",
                    "[loadh]",
                    "[storeh]",
                    "[memmoveh]",
                )
            ):
                continue
            data = self.parser.parse_line_detached(line, line_num)
            if data is not None:
                yield data


class TraceRow:
    __slots__ = ("schema_name", "data")

    def __init__(self, schema_name: str, data: Dict[str, object]):
        self.schema_name = schema_name
        self.data = data

    def __getitem__(self, key: str):
        return self.data[key]


class CustomLogParser:
    def __init__(self, fp: TextIO):
        # The sbsv package materializes the whole trace in memory.  BinRadar
        # traces can be many GB, so the type analyzer consumes only the schemas
        # it needs and yields rows as it scans the file.
        self.fp = fp
        self.rows_seen = 0
        self.rows_parsed = 0

    def get_result_in_order(self) -> Iterator[TraceRow]:
        for line in self.fp:
            self.rows_seen += 1
            row = self._parse_line(line)
            if row is None:
                continue
            self.rows_parsed += 1
            yield row

    @staticmethod
    def _tokens(line: str) -> List[str]:
        tokens: List[str] = []
        pos = 0
        while True:
            start = line.find("[", pos)
            if start < 0:
                break
            end = line.find("]", start + 1)
            if end < 0:
                break
            tokens.append(line[start + 1 : end])
            pos = end + 1
        return tokens

    @staticmethod
    def _hex(value: str) -> int:
        return int(value, 16)

    @staticmethod
    def _int(value: str) -> int:
        return int(value, 10)

    @staticmethod
    def _bool(value: str) -> bool:
        value = value.strip().lower()
        if value in ("true", "t"):
            return True
        if value in ("false", "f"):
            return False
        return int(value, 0) != 0

    @staticmethod
    def _field_map(tokens: List[str], start: int) -> Dict[str, str]:
        fields: Dict[str, str] = {}
        for token in tokens[start:]:
            parts = token.split(None, 1)
            if len(parts) == 2:
                fields[parts[0]] = parts[1]
        return fields

    def _parse_line(self, line: str) -> Optional[TraceRow]:
        if not line or line[0] != "[":
            return None
        if not line.startswith(
            (
                "[alloc]",
                "[calloc]",
                "[free]",
                "[stack]",
                "[global]",
                "[loadh]",
                "[storeh]",
                "[memmoveh]",
            )
        ):
            return None

        tokens = self._tokens(line)
        if not tokens:
            return None
        head = tokens[0]

        try:
            if head == "alloc" and len(tokens) > 1 and tokens[1] == "start":
                f = self._field_map(tokens, 2)
                return TraceRow(
                    "alloc$start",
                    {
                        "base": self._hex(f["base"]),
                        "size": self._hex(f["size"]),
                        "pc": self._hex(f["pc"]),
                    },
                )
            if head == "calloc":
                f = self._field_map(tokens, 1)
                return TraceRow(
                    "calloc",
                    {
                        "size": self._hex(f["size"]),
                        "pc": self._hex(f["pc"]),
                    },
                )
            if head == "free" and len(tokens) > 1 and tokens[1] == "done":
                f = self._field_map(tokens, 2)
                return TraceRow(
                    "free$done",
                    {
                        "base": self._hex(f["base"]),
                        "pc": self._hex(f["pc"]),
                    },
                )
            if head == "stack" and len(tokens) > 1 and tokens[1] == "push":
                f = self._field_map(tokens, 2)
                return TraceRow(
                    "stack$push",
                    {
                        "sp": self._hex(f["sp"]),
                        "size": self._hex(f["size"]),
                        "pc": self._hex(f["pc"]),
                        "depth": self._int(f["depth"]),
                        "sr-base": self._hex(f["sr-base"]),
                        "sr-size": self._hex(f["sr-size"]),
                    },
                )
            if head == "stack" and len(tokens) > 1 and tokens[1] == "pop":
                f = self._field_map(tokens, 2)
                return TraceRow(
                    "stack$pop",
                    {
                        "sp": self._hex(f["sp"]),
                        "base": self._hex(f["base"]),
                        "pc": self._hex(f["pc"]),
                        "depth": self._int(f["depth"]),
                    },
                )
            if head == "global" and len(tokens) > 1 and tokens[1] == "add":
                f = self._field_map(tokens, 2)
                return TraceRow(
                    "global$add",
                    {
                        "base": self._hex(f["base"]),
                        "size": self._hex(f["size"]),
                        "name": f.get("name", "unknown"),
                    },
                )
            if head in ("loadh", "storeh") and len(tokens) > 1:
                sub = tokens[1]
                if sub in ("val", "val-fallback"):
                    f = self._field_map(tokens, 2)
                    return TraceRow(
                        f"{head}${sub}",
                        {
                            "reg": f["reg"],
                            "pc": self._hex(f["pc"]),
                            "addr": self._hex(f["addr"]),
                            "base": self._hex(f["base"]),
                            "disp": self._int(f["disp"]),
                            "reg-base": self._hex(f["reg-base"]),
                            "size": self._hex(f["size"]),
                            "val": self._hex(f["val"]),
                            "is-ptr": self._bool(f["is-ptr"]),
                        },
                    )
                if sub == "inval":
                    f = self._field_map(tokens, 2)
                    return TraceRow(
                        f"{head}$inval",
                        {
                            "reg": f["reg"],
                            "pc": self._hex(f["pc"]),
                            "addr": self._hex(f["addr"]),
                            "reg-base": self._hex(f["reg-base"]),
                            "size": self._hex(f["size"]),
                            "val": self._hex(f["val"]),
                            "is-ptr": self._bool(f["is-ptr"]),
                        },
                    )
            if head == "memmoveh":
                f = self._field_map(tokens, 1)
                return TraceRow(
                    "memmoveh",
                    {
                        "src": self._hex(f["src"]),
                        "dst": self._hex(f["dst"]),
                        "size": self._hex(f["size"]),
                        "val": self._hex(f["val"]),
                        "is-ptr": self._bool(f["is-ptr"]),
                        "src-r": f["src-r"],
                        "src-rb": self._hex(f["src-rb"]),
                        "dst-r": f["dst-r"],
                        "dst-rb": self._hex(f["dst-rb"]),
                    },
                )
        except (KeyError, ValueError):
            return None
        return None


def test_efficiency():
    log_file = os.path.join(RESOURCE_DIR, "benchmark.sbsv")
    start_time = time.time()
    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        parser = CustomLogParser(f)
        num = 1
        for _ in parser.get_result_in_order():
            num += 1
    elapsed = int((time.time() - start_time) * 1000)
    print(
        f"CustomLogParser: parsed {num} rows (seen {parser.rows_seen}) in {elapsed} ms"
    )
    start_time = time.time()
    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        parser = SbsvLogParser(f)
        num = 1
        for _ in parser.get_result_in_order():
            num += 1
    elapsed = int((time.time() - start_time) * 1000)
    print(f"SbsvLogParser: parsed {num} rows (seen {parser.rows_seen}) in {elapsed} ms")


if __name__ == "__main__":
    test_efficiency()
