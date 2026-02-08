"""Compile .po files to .mo files without requiring gettext tools."""
import struct
import os


def parse_po(po_path):
    messages = []
    current_msgid = None
    current_msgstr = None
    in_msgid = False
    in_msgstr = False

    with open(po_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                continue
            if not line:
                if current_msgid is not None and current_msgstr is not None:
                    messages.append((current_msgid, current_msgstr))
                current_msgid = None
                current_msgstr = None
                in_msgid = False
                in_msgstr = False
                continue
            if line.startswith('msgid '):
                if current_msgid is not None and current_msgstr is not None:
                    messages.append((current_msgid, current_msgstr))
                current_msgid = line[6:].strip('"')
                current_msgstr = None
                in_msgid = True
                in_msgstr = False
            elif line.startswith('msgstr '):
                current_msgstr = line[7:].strip('"')
                in_msgid = False
                in_msgstr = True
            elif line.startswith('"') and line.endswith('"'):
                val = line[1:-1]
                if in_msgid:
                    current_msgid += val
                elif in_msgstr:
                    current_msgstr += val

        if current_msgid is not None and current_msgstr is not None:
            messages.append((current_msgid, current_msgstr))

    return messages


def write_mo(messages, mo_path):
    messages.sort(key=lambda x: x[0])
    offsets = []
    ids = b''
    strs = b''
    key_start = 0
    val_start = 0

    for msgid, msgstr in messages:
        msgid_bytes = msgid.encode('utf-8')
        msgstr_bytes = msgstr.encode('utf-8')
        offsets.append((key_start, len(msgid_bytes), val_start, len(msgstr_bytes)))
        ids += msgid_bytes + b'\x00'
        strs += msgstr_bytes + b'\x00'
        key_start += len(msgid_bytes) + 1
        val_start += len(msgstr_bytes) + 1

    n = len(messages)
    keystart = 28 + n * 8 * 2
    valstart = keystart + len(ids)

    with open(mo_path, 'wb') as fout:
        fout.write(struct.pack('Iiiiiii', 0x950412de, 0, n, 28, 28 + n * 8, 0, 0))
        for o in offsets:
            fout.write(struct.pack('ii', o[1], keystart + o[0]))
        for o in offsets:
            fout.write(struct.pack('ii', o[3], valstart + o[2]))
        fout.write(ids)
        fout.write(strs)


if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    for lang in ['en', 'fr']:
        po = os.path.join(base, 'locale', lang, 'LC_MESSAGES', 'django.po')
        mo = os.path.join(base, 'locale', lang, 'LC_MESSAGES', 'django.mo')
        if os.path.exists(po):
            msgs = parse_po(po)
            write_mo(msgs, mo)
            print(f'{lang}: {len(msgs)} messages compiled -> {mo}')
        else:
            print(f'{lang}: {po} not found, skipping')
