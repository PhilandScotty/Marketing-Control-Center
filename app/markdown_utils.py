from __future__ import annotations

import html
import re
from markupsafe import Markup


def _format_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code class=\"font-mono text-mcc-accent\">\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong class=\"text-mcc-text\">\1</strong>", escaped)
    return escaped


def render_markdown_lite(markdown_text: str) -> Markup:
    lines = markdown_text.splitlines()
    parts: list[str] = []
    list_type: str | None = None
    in_code = False
    code_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            parts.append(
                f"<p class=\"text-sm text-mcc-muted leading-6\">{_format_inline(' '.join(paragraph))}</p>"
            )
            paragraph = []

    def flush_list() -> None:
        nonlocal list_type
        if list_type:
            parts.append(f"</{list_type}>")
            list_type = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                parts.append(
                    "<pre class=\"rounded-lg bg-mcc-bg p-3 overflow-x-auto text-xs text-mcc-text font-mono\">"
                    f"{html.escape(chr(10).join(code_lines))}</pre>"
                )
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        if stripped.startswith("### "):
            flush_paragraph()
            flush_list()
            parts.append(f"<h4 class=\"text-sm font-semibold text-mcc-text mt-4 mb-2\">{_format_inline(stripped[4:])}</h4>")
            continue

        if stripped.startswith("## "):
            flush_paragraph()
            flush_list()
            parts.append(f"<h3 class=\"text-base font-semibold text-mcc-text mt-5 mb-2\">{_format_inline(stripped[3:])}</h3>")
            continue

        if re.match(r"^\d+\.\s+", stripped):
            flush_paragraph()
            if list_type != "ol":
                flush_list()
                list_type = "ol"
                parts.append("<ol class=\"list-decimal pl-5 space-y-1 text-sm text-mcc-muted\">")
            item = re.sub(r"^\d+\.\s+", "", stripped)
            parts.append(f"<li>{_format_inline(item)}</li>")
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            if list_type != "ul":
                flush_list()
                list_type = "ul"
                parts.append("<ul class=\"list-disc pl-5 space-y-1 text-sm text-mcc-muted\">")
            parts.append(f"<li>{_format_inline(stripped[2:])}</li>")
            continue

        paragraph.append(stripped)

    flush_paragraph()
    flush_list()

    if in_code:
        parts.append(
            "<pre class=\"rounded-lg bg-mcc-bg p-3 overflow-x-auto text-xs text-mcc-text font-mono\">"
            f"{html.escape(chr(10).join(code_lines))}</pre>"
        )

    return Markup("".join(parts))
