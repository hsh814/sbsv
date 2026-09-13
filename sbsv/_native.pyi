from typing import Any, Dict, List, Optional, Sequence, Tuple


def parse_rows(
    content: str,
    schemas: Sequence[str],
    ignore_unknown: bool = ...,
    ignored_prefix: Optional[str] = ...,
    save_ignored: bool = ...,
) -> List[Tuple[str, Dict[str, Any]]]: ...


def version() -> Tuple[int, int, int]: ...
