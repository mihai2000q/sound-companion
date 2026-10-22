"""The structured error every music tool returns for bad input. Never a guess, never an exception."""

GERMAN_H_HINT = "In German notation H is B and B is Bb; this tool takes English note names (C D E F G A B)."


def tool_error(error: str, message: str) -> dict:
    return {"error": error, "message": message}
