"""Compile .po files to .mo files.
Pure Python implementation — no external tools required.
Properly handles UTF-8 encoded .po files with accented characters.
"""
import array
import os
import struct
import sys


def parse_po(po_path):
    """Parse a .po file and return a list of (msgid, msgstr) tuples."""
    messages = []
    current_msgid = None
    current_msgstr = None
    in_msgid = False
    in_msgstr = False

    with open(po_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()

        # Skip comments and empty lines
        if line.startswith('#') or not line:
            if in_msgstr and current_msgid is not None:
                messages.append((current_msgid, current_msgstr or ''))
                current_msgid = None
                current_msgstr = None
                in_msgid = False
                in_msgstr = False
            continue

        if line.startswith('msgid '):
            if in_msgstr and current_msgid is not None:
                messages.append((current_msgid, current_msgstr or ''))
            in_msgid = True
            in_msgstr = False
            current_msgid = _extract_string(line[6:])
            current_msgstr = None
        elif line.startswith('msgstr '):
            in_msgid = False
            in_msgstr = True
            current_msgstr = _extract_string(line[7:])
        elif line.startswith('"') and line.endswith('"'):
            s = _extract_string(line)
            if in_msgid:
                current_msgid = (current_msgid or '') + s
            elif in_msgstr:
                current_msgstr = (current_msgstr or '') + s

    # Don't forget the last entry
    if current_msgid is not None:
        messages.append((current_msgid, current_msgstr or ''))

    return messages


def _extract_string(s):
    """Extract the string content from a quoted .po line."""
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    # Process escape sequences
    s = s.replace('\\n', '\n')
    s = s.replace('\\t', '\t')
    s = s.replace('\\"', '"')
    s = s.replace('\\\\', '\\')
    return s


def compile_po_to_mo(po_path, mo_path):
    """Compile a .po file to a .mo file (pure Python, UTF-8 safe)."""
    messages = parse_po(po_path)

    # The .mo file format:
    # - Magic number
    # - Version
    # - Number of strings
    # - Offset of table with original strings
    # - Offset of table with translation strings
    # - Size of hashing table (0 = no hashing)
    # - Offset of hashing table

    # Sort messages by msgid (required by .mo format for binary search)
    # The empty string (header) must come first
    header_entry = None
    regular_entries = []
    for msgid, msgstr in messages:
        if msgid == '':
            header_entry = (msgid, msgstr)
        else:
            regular_entries.append((msgid, msgstr))

    regular_entries.sort(key=lambda x: x[0].encode('utf-8'))

    if header_entry:
        sorted_messages = [header_entry] + regular_entries
    else:
        sorted_messages = regular_entries

    # Encode all strings as UTF-8 bytes
    offsets = []
    ids = b''
    strs = b''
    for msgid, msgstr in sorted_messages:
        msgid_bytes = msgid.encode('utf-8')
        msgstr_bytes = msgstr.encode('utf-8')
        offsets.append((len(ids), len(msgid_bytes), len(strs), len(msgstr_bytes)))
        ids += msgid_bytes + b'\x00'
        strs += msgstr_bytes + b'\x00'

    # Generate the .mo file
    n = len(sorted_messages)
    # Header: 7 * 4 bytes = 28 bytes
    # Then: n entries for originals table (each 2 * 4 bytes) = n * 8
    # Then: n entries for translations table (each 2 * 4 bytes) = n * 8
    # Then: ids data
    # Then: strs data
    keystart = 28
    valuestart = keystart + n * 8
    koffsets = []
    voffsets = []
    ids_start = valuestart + n * 8
    strs_start = ids_start + len(ids)

    for o in offsets:
        koffsets.append((o[1], ids_start + o[0]))
        voffsets.append((o[3], strs_start + o[2]))

    output = struct.pack(
        'Iiiiiii',
        0x950412de,  # Magic number (little-endian)
        0,           # Version
        n,           # Number of strings
        keystart,    # Offset of originals table
        valuestart,  # Offset of translations table
        0,           # Size of hashing table
        0,           # Offset of hashing table
    )

    for length, offset in koffsets:
        output += struct.pack('ii', length, offset)
    for length, offset in voffsets:
        output += struct.pack('ii', length, offset)

    output += ids
    output += strs

    with open(mo_path, 'wb') as f:
        f.write(output)


def compile_all():
    """Compile all .po files in the locale directory."""
    base = os.path.dirname(os.path.abspath(__file__))
    success = True
    for lang in ['en', 'fr']:
        po = os.path.join(base, 'locale', lang, 'LC_MESSAGES', 'django.po')
        mo = os.path.join(base, 'locale', lang, 'LC_MESSAGES', 'django.mo')
        if os.path.exists(po):
            try:
                compile_po_to_mo(po, mo)
                print(f'{lang}: compiled -> {mo}')
            except Exception as e:
                print(f'{lang}: compilation failed: {e}')
                import traceback
                traceback.print_exc()
                success = False
        else:
            print(f'{lang}: {po} not found, skipping')
    return success


if __name__ == '__main__':
    print("Compiling .po files to .mo (pure Python, UTF-8)...")
    if compile_all():
        print("Done! All .mo files compiled successfully.")
    else:
        print("ERROR: Some compilations failed.")
        sys.exit(1)
