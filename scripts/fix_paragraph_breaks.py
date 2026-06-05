#!/usr/bin/env python3
"""
Fix improper paragraph breaks by joining fragments
"""

from pathlib import Path

TEXT_PATH = Path("data/text/anjos-angelicos-sicarios.txt")
content = TEXT_PATH.read_text(encoding='utf-8')
lines = content.split('\n')

print("FIXING PARAGRAPH BREAKS")
print("=" * 80)

# Join fragments: if a line doesn't end with punctuation, join with next
fixed_lines = []
i = 0

while i < len(lines):
    line = lines[i].strip()

    if not line:
        fixed_lines.append("")
        i += 1
        continue

    # Check if this line is a fragment (doesn't end with ., !, ?, :, ", or »)
    # and if next line exists and doesn't start with capital letter (mid-sentence)
    if i + 1 < len(lines):
        next_line = lines[i + 1].strip()

        # Fragment detection:
        # - Current line doesn't end with ending punctuation
        # - Current line doesn't end with dash
        # - Next line exists and is not empty
        # - Next line doesn't look like a heading (not all caps or very short)
        if (line and
            not line.endswith(('.', '!', '?', ':', '"', '»', '—', '-')) and
            next_line and
            not (len(next_line) < 50 and next_line.isupper())):  # Not a heading

            # Join lines
            combined = line + " " + next_line
            fixed_lines.append(combined)
            i += 2
            continue

    fixed_lines.append(line)
    i += 1

# Remove excess blank lines
final_lines = []
prev_blank = False

for line in fixed_lines:
    if not line.strip():
        if not prev_blank:
            final_lines.append("")
            prev_blank = True
    else:
        final_lines.append(line)
        prev_blank = False

# Save
result = '\n'.join(final_lines)
TEXT_PATH.write_text(result, encoding='utf-8')

before_count = len(lines)
after_count = len(final_lines)

print(f"Lines before: {before_count}")
print(f"Lines after: {after_count}")
print(f"Joined fragments: {before_count - after_count}")
print("\nFixed!")
