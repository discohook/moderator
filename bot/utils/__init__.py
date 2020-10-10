import difflib
from typing import Optional, Union

from discord.utils import escape_markdown


def wrap_in_code(value: str, *, block: Optional[Union[bool, str]] = None):
    value = value.replace("`", "\u200b`\u200b")
    value = value.replace("\u200b\u200b", "\u200b")

    if block is None:
        return "``" + value + "``"

    lang = "" if block is True else block

    return f"```{block}\n" + value + "\n```"


def diff_message(a: str, b: str):
    a_words = a.split()
    b_words = b.split()

    matcher = difflib.SequenceMatcher(autojunk=False)
    matcher.set_seqs(a_words, b_words)

    groups = []

    for group in matcher.get_grouped_opcodes():
        parts = []

        for op, i1, i2, j1, j2 in group:
            if op == "delete" or op == "replace":
                parts.append(f"~~{escape_markdown(' '.join(a_words[i1:i2]))}~~")
            if op == "insert" or op == "replace":
                parts.append(f"__{escape_markdown(' '.join(b_words[j1:j2]))}__")
            if op == "equal":
                parts.append(escape_markdown(" ".join(a_words[i1:i2])))

        groups.append(" ".join(parts))

    return " [...] ".join(groups)
