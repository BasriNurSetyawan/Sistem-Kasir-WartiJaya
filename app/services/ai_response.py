"""Shared style contract and output cleanup for Copilot responses."""

import re


SYSTEM_INSTRUCTION = (
    "Jawab dalam bahasa Indonesia yang natural, santai, sopan, dan ringkas, seperti "
    "percakapan biasa dengan pemilik toko. Gunakan paragraf pendek. Jangan gunakan "
    "Markdown atau simbol format seperti #, ###, **, *, -, --, backtick, daftar, "
    "atau tabel. Jangan gunakan emoji dekoratif."
)

_EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0xFE00, 0xFE0F), (0x1F1E6, 0x1F1FF))
_EMOJI_CODEPOINTS = {0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D, 0x3297, 0x3299}


def _is_decorative_emoji(char):
    codepoint = ord(char)
    return (
        char in ('\u200d', '\u20e3')
        or codepoint in _EMOJI_CODEPOINTS
        or any(start <= codepoint <= end for start, end in _EMOJI_RANGES)
    )


def clean_response(value):
    """Remove common Markdown and decorative emoji while preserving paragraphs."""
    if not isinstance(value, str):
        return ''
    value = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', value)
    paragraphs = []
    for paragraph in re.split(r'\n\s*\n', value.strip()):
        lines = []
        for line in paragraph.splitlines():
            line = re.sub(r'^\s{0,3}#{1,6}\s*', '', line)
            line = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*)', '', line)
            line = re.sub(r'\*\*(.*?)\*\*|__(.*?)__', lambda m: m.group(1) or m.group(2), line)
            line = re.sub(r'\*(.*?)\*|_(.*?)_', lambda m: m.group(1) or m.group(2), line)
            line = line.replace('`', '').replace('#', '').replace('*', '').replace('_', '').replace('|', ' ')
            line = re.sub(r'--+', ' ', line)
            line = ''.join(' ' if _is_decorative_emoji(char) else char for char in line)
            line = re.sub(r'\s+', ' ', line).strip()
            if line and not re.fullmatch(r'[-*_\s]+', line):
                lines.append(line)
        if lines:
            paragraphs.append(' '.join(lines))
    return '\n\n'.join(paragraphs).strip()
