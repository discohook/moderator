import difflib
import re
from typing import Optional, Union

from discord.utils import escape_markdown


def wrap_in_code(value: str, *, block: Optional[Union[bool, str]] = None):
    value = value.replace("`", "\u200b`\u200b")
    value = value.replace("\u200b\u200b", "\u200b")

    if block is None:
        return "``" + value + "``"

    lang = "" if block is True else block

    return f"```{block}\n" + value + "\n```"


def escape(text: str):
    return escape_markdown(re.sub(r"<(a?:\w+:\d+)>", "<\u200b\\1>", text))


def cut_words(text: str, max_len: int, *, end: str = "..."):
    words = [""] + re.split(r"(\s+)", text)

    result = ""

    if len(words[1] + end) > max_len:
        return words[1][: max_len - len(end)] + end

    for last_sep, word in zip(words[::2], words[1::2]):
        if len(result + last_sep + word + end) > max_len:
            return result + end

        result += last_sep + word

    return words


def diff_message(
    a: str,
    b: str,
    *,
    max_len: Optional[int] = None,
    group_sep: str = "**...**",
    cutoff_end: str = " **... [cut off]**",
):
    a_words = a.split()
    b_words = b.split()

    matcher = difflib.SequenceMatcher(autojunk=False)
    matcher.set_seqs(a_words, b_words)

    groups = []

    start = f"{group_sep} "
    end = f" {group_sep}"

    for group in matcher.get_grouped_opcodes():
        parts = []

        for op, i1, i2, j1, j2 in group:
            if min(i1, j1) == 0:
                start = ""
            if i2 == len(a) - 1 or j2 == len(b) - 1:
                end = ""

            if op == "delete" or op == "replace":
                parts.append(f"~~{escape(' '.join(a_words[i1:i2]))}~~")
            if op == "insert" or op == "replace":
                parts.append(f"__{escape(' '.join(b_words[j1:j2]))}__")
            if op == "equal":
                parts.append(escape(" ".join(a_words[i1:i2])))

        groups.append(" ".join(parts))

    res = start + f" {group_sep} ".join(groups) + end
    if max_len:
        res = cut_words(res, max_len, end=cutoff_end)
    return res
