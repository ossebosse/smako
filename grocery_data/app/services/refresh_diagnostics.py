"""Bounded source failure evidence without locals, HTTP bodies or credentials."""

import re
from pathlib import Path


def source_failure_diagnostic(error: BaseException, *, depth: int = 0) -> dict:
    frames = []
    literals = set()
    trace = error.__traceback__
    while trace is not None:
        code = trace.tb_frame.f_code
        frames.append(
            {"file": Path(code.co_filename).name, "function": code.co_name, "line": trace.tb_lineno}
        )
        literals.update(value for value in code.co_consts if isinstance(value, str))
        trace = trace.tb_next
    message = str(error)
    # Only verbatim source-code literals qualify. Never copy interpolated
    # provider errors, parser inputs, Pydantic values, request URLs or bodies.
    safe = message in literals and not re.search(
        r"authorization|bearer|cookie|password|secret|token|api.key|https?://",
        message,
        re.IGNORECASE,
    )
    result = {
        "type": type(error).__name__,
        "message": message if safe else "nonliteral exception text omitted",
        "stack": frames[-32:],
    }
    cause = error.__cause__ or (error.__context__ if not error.__suppress_context__ else None)
    if cause is not None:
        result["cause_type"] = type(cause).__name__
        if depth < 7:
            result["cause"] = source_failure_diagnostic(cause, depth=depth + 1)
    return result
