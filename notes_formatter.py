"""
notes_formatter.py

Small CLI tool to convert slide-style .txt notes into a speaker-friendly .md file.

Usage examples:
    python notes_formatter.py notes_intro.txt
    python notes_formatter.py notes_intro.txt -o notes_intro.md --wrap 90

Behavior (heuristics):
- Splits the input by lines like: --- Slide 1 ---
- For each slide, picks the first non-empty line as a candidate title if it's short (<12 words and not a sentence).
- Converts lines starting with '-', '*', '•' or numbered lists into markdown lists, preserving nesting by indentation.
- Wraps paragraphs to a configurable width (default 100) for teleprompter readability.
- Outputs a markdown file with a heading for each slide and nicely formatted content.

This is intentionally conservative: it preserves most of the original text while making lists and titles explicit.
"""

from __future__ import annotations
import argparse
import re
import textwrap
from pathlib import Path
from typing import List, Tuple

SLIDE_HEADER_RE = re.compile(r"^---\s*Slide\s*\d+\s*---\s*$", re.IGNORECASE | re.MULTILINE)
LIST_ITEM_RE = re.compile(r"^(?P<indent>\s*)(?:[-\*•]|(?P<number>\d+)\.)\s*(?P<text>.*)$")


def split_slides(text: str) -> List[str]:
    """
    Splits the input text into slides using a robust regex for the separator
    `--- Slide XXX ---` (matches even if not on its own line).
    Returns a list of slide strings (trimmed).
    """
    import re
    pattern = re.compile(r'---\s*Slide\s*\d+\s*---', re.IGNORECASE)
    matches = list(pattern.finditer(text))

    if not matches:
        return [text.strip()] if text.strip() else []

    slides: List[str] = []
    # any leading text before first match
    leading = text[: matches[0].start()].strip()
    if leading:
        slides.append(leading)

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        slides.append(text[start:end].strip())

    return slides


def is_title_candidate(line: str) -> bool:
    """Heuristic to decide if a line is a slide title.
    Title if it's short (<12 words), doesn't end with a period, and isn't a list.
    """
    if not line:
        return False
    if LIST_ITEM_RE.match(line):
        return False
    words = line.strip().split()
    if len(words) > 12:
        return False
    if line.strip().endswith('.') or line.strip().endswith(':'):
        return False
    # If it contains many lowercase leading words, still okay; we avoid aggressive checks
    return True


def format_list_lines(lines: List[str]) -> List[str]:
    """Convert plain-text list-like lines into markdown list lines preserving nesting.
    Lines matching LIST_ITEM_RE are converted; other lines are returned unchanged.
    """
    out: List[str] = []
    for line in lines:
        m = LIST_ITEM_RE.match(line)
        if m:
            indent = m.group('indent') or ''
            text = m.group('text') or ''
            # Determine nesting level: 4 spaces per level (common in these notes)
            level = len(indent.replace('\t', '    ')) // 4
            md_indent = '    ' * level
            # Use '-' for bullet lists; numbered lists preserve number if present
            if m.group('number'):
                marker = f"{m.group('number')}."
            else:
                marker = '-'
            out.append(f"{md_indent}{marker} {text.strip()}")
        else:
            out.append(line)
    return out


def wrap_paragraphs(text: str, width: int = 100) -> str:
    """Wrap paragraphs to the given width while preserving lists and blank lines.
    - List lines (starting with '-' or numbered) are not reflowed except their text part.
    - Paragraphs are reflowed using textwrap.fill.
    """
    lines = text.splitlines()
    result_lines: List[str] = []
    paragraph: List[str] = []

    def flush_paragraph():
        if not paragraph:
            return
        joined = ' '.join(l.strip() for l in paragraph)
        wrapped = textwrap.fill(joined, width=width)
        result_lines.extend(wrapped.splitlines())

    for ln in lines:
        if ln.strip() == '':
            flush_paragraph()
            paragraph = []
            result_lines.append('')
            continue
        if LIST_ITEM_RE.match(ln):
            # flush any pending paragraph then append list line (do not wrap the marker heavily)
            flush_paragraph()
            paragraph = []
            # Rewrap only the text portion of the list to the width minus marker
            m = LIST_ITEM_RE.match(ln)
            indent = m.group('indent') or ''
            number = m.group('number')
            text_part = m.group('text') or ''
            if number:
                marker = f"{number}. "
            else:
                marker = '- '
            prefix = indent + marker
            wrapped_text = textwrap.fill(text_part.strip(), width=width - len(prefix))
            wrapped_lines = wrapped_text.splitlines()
            # first line with prefix, subsequent with spaces aligned under text
            if wrapped_lines:
                result_lines.append(prefix + wrapped_lines[0])
                pad = ' ' * len(prefix)
                for l in wrapped_lines[1:]:
                    result_lines.append(pad + l)
            else:
                result_lines.append(prefix.rstrip())
            continue
        # otherwise accumulate paragraph lines
        paragraph.append(ln)
    flush_paragraph()
    return '\n'.join(result_lines)


def process_slide(slide_text: str, slide_index: int, wrap: int = 100) -> str:
    """Convert a single slide block into markdown text with heading and formatted body."""
    # Split into lines and strip uniform leading/trailing blank lines
    lines = slide_text.splitlines()
    # Remove common leading indentation
    stripped_lines = [ln.rstrip() for ln in lines]
    # Find first non-empty line
    first_non_empty = None
    for ln in stripped_lines:
        if ln.strip():
            first_non_empty = ln.strip()
            break
    title = None
    body_lines = stripped_lines
    if first_non_empty and is_title_candidate(first_non_empty):
        title = first_non_empty
        # drop the first occurrence from body
        dropped = False
        new_body = []
        for ln in stripped_lines:
            if not dropped and ln.strip() == first_non_empty:
                dropped = True
                continue
            new_body.append(ln)
        body_lines = new_body
    # Convert list-like lines
    body_lines = format_list_lines(body_lines)
    body_text = '\n'.join(body_lines).strip()
    # Wrap paragraphs but preserve markdown lists
    body_text = wrap_paragraphs(body_text, width=wrap)

    # Compose markdown for slide
    header = f"## Slide {slide_index+1}"
    if title:
        header += f" — {title}"
    parts = [header, '']
    if body_text:
        parts.append(body_text)
    else:
        parts.append('_(no notes)_')
    parts.append('')
    return '\n'.join(parts)


def convert_text_to_markdown(text: str, wrap: int = 100) -> str:
    slides = split_slides(text)
    md_parts = [f"# Speaker Notes\n"]
    for i, s in enumerate(slides):
        md_parts.append(process_slide(s, i, wrap=wrap))
    return '\n'.join(md_parts).strip() + '\n'


def main():
    p = argparse.ArgumentParser(description='Convert slide-style .txt notes into speaker-friendly .md')
    p.add_argument('inputs', nargs='+', help='One or more input .txt files')
    p.add_argument('-o', '--output', help='Output .md file (if multiple inputs, this becomes a directory)')
    p.add_argument('--wrap', type=int, default=100, help='Wrap width for paragraphs (default 100)')
    args = p.parse_args()

    inputs = [Path(x) for x in args.inputs]
    # If multiple inputs and output provided, treat output as directory
    if len(inputs) > 1:
        out_dir = Path(args.output) if args.output else Path('.')
        out_dir.mkdir(parents=True, exist_ok=True)
        for inp in inputs:
            text = inp.read_text(encoding='utf-8')
            md = convert_text_to_markdown(text, wrap=args.wrap)
            out_path = out_dir / (inp.stem + '.md')
            out_path.write_text(md, encoding='utf-8')
            print(f'Wrote {out_path}')
    else:
        inp = inputs[0]
        text = inp.read_text(encoding='utf-8')
        md = convert_text_to_markdown(text, wrap=args.wrap)
        if args.output:
            out_path = Path(args.output)
            # If output ends with / or is a directory, place file inside
            if args.output.endswith('/') or out_path.exists() and out_path.is_dir():
                out_path.mkdir(parents=True, exist_ok=True)
                out_path = out_path / (inp.stem + '.md')
        else:
            out_path = inp.with_suffix('.md')
        out_path.write_text(md, encoding='utf-8')
        print(f'Wrote {out_path}')


if __name__ == '__main__':
    main()
