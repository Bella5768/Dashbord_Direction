"""
Audit i18n complet — liste tout texte visible non internationalisé.
Usage: python scripts/audit_i18n.py > audit.txt
"""
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR  = os.path.join(ROOT, 'templates')
CORE_DIR = os.path.join(ROOT, 'core')

issues = []  # (file, line, kind, text)

def add(f, n, kind, text):
    text = text.strip()
    if text:
        issues.append((f.replace(ROOT + os.sep, ''), n, kind, text))

# ─── helpers ──────────────────────────────────────────────────────────────────
SKIP_TAGS = re.compile(
    r'\{%\s*(trans|blocktrans|load|if|else|elif|endif|for|endfor|block|endblock'
    r'|url|static|with|endwith|csrf_token|include|extends|comment|endcomment'
    r'|empty|plural|endblocktrans|spaceless|endspaceless|now)[^%]*%\}'
)
TRANS_WRAPPED = re.compile(r'\{%[-\s]*trans\s+["\'][^"\']+["\'][-\s]*%\}')
BTRANS       = re.compile(r'\{%\s*blocktrans[^%]*%\}.*?\{%\s*endblocktrans\s*%\}', re.DOTALL)
VAR_TAG      = re.compile(r'\{\{[^}]+\}\}')
HTML_TAG     = re.compile(r'<[^>]+>')
COMMENT_TAG  = re.compile(r'\{#[^#]*#\}')

# French-ish: contains a letter and is not purely code/number/url/path
HAS_LETTER   = re.compile(r'[a-zA-ZÀ-ÿ]{3,}')
LOOKS_FRENCH = re.compile(
    r'[ÀàÂâÄäÇçÈèÉéÊêËëÎîÏïÔôÙùÛûÜü]'          # accented char
    r'|(?<![a-z])(le|la|les|un|une|des|du|de|et|en|au|aux|est|son|sa|ses|'
    r'ce|cet|cette|ces|je|tu|il|nous|vous|ils|pas|plus|pour|dans|par|sur|'
    r'avec|sans|ou|mais|donc|car|si|que|qui|quoi|dont|où|mon|ton|'
    r'votre|notre|leur|leurs|tout|tous|toute|toutes|très|bien|mal|non|oui|'
    r'aucun|aucune|chaque|même|autre|autres)(?![a-z])',
    re.IGNORECASE
)

def is_meaningful_text(s):
    s = s.strip()
    if len(s) < 3:
        return False
    if not HAS_LETTER.search(s):
        return False
    # Skip pure slugs / code values / URLs
    if re.fullmatch(r'[\w\-\_\.\/\:]+', s):
        return False
    # Skip JS/CSS snippets
    if re.search(r'[{}();,]', s):
        return False
    return True

def strip_template_tags(s):
    s = BTRANS.sub('', s)
    s = TRANS_WRAPPED.sub('', s)
    s = SKIP_TAGS.sub('', s)
    s = VAR_TAG.sub('', s)
    s = COMMENT_TAG.sub('', s)
    return s

# ─── TEMPLATES ────────────────────────────────────────────────────────────────

ATTR_WITH_TEXT = re.compile(
    r'(?:title|placeholder|alt|aria-label|data-confirm|data-delete-type|'
    r'data-confirm-title|data-confirm-label|data-bs-title)\s*=\s*["\']([^"\']{3,})["\']',
    re.IGNORECASE
)
ATTR_WITH_TRANS = re.compile(
    r'(?:title|placeholder|alt|aria-label|data-confirm|data-delete-type|'
    r'data-confirm-title|data-confirm-label)\s*=\s*"[^"]*\{%\s*trans',
    re.IGNORECASE
)

def audit_template(fpath):
    rel = fpath.replace(ROOT + os.sep, '')
    with open(fpath, encoding='utf-8', errors='replace') as f:
        src = f.read()

    lines = src.split('\n')

    for lno, raw_line in enumerate(lines, 1):
        line = raw_line

        # Skip pure template control lines
        if re.fullmatch(r'\s*\{%[^%]*%\}\s*', line.strip()):
            continue

        # 1. Check text content between HTML tags
        content = strip_template_tags(line)
        content = HTML_TAG.sub('\n', content)
        for fragment in content.split('\n'):
            fragment = fragment.strip()
            if not fragment:
                continue
            if not is_meaningful_text(fragment):
                continue
            if LOOKS_FRENCH.search(fragment) or (HAS_LETTER.search(fragment) and len(fragment) > 6):
                # Ignore if it's inside a known-translated block
                add(rel, lno, 'TEXT', fragment[:100])

        # 2. Check HTML attributes
        for m in ATTR_WITH_TEXT.finditer(raw_line):
            val = m.group(1).strip()
            if not val or val.startswith('{%') or '{{' in val:
                continue
            if LOOKS_FRENCH.search(val) or (HAS_LETTER.search(val) and len(val) > 6):
                add(rel, lno, 'ATTR', f'{m.group(0)[:80]}')

        # 3. data-delete-type / data-confirm without {% trans %}
        for attr in ['data-delete-type', 'data-confirm']:
            pat = re.compile(rf'{attr}=["\']([^"\'{{]+)["\']')
            for m in pat.finditer(raw_line):
                val = m.group(1).strip()
                if val and LOOKS_FRENCH.search(val):
                    add(rel, lno, 'DATA-ATTR', f'{attr}="{val}"')

# ─── PYTHON (views / models / decorators) ─────────────────────────────────────

FSTRING_MSG = re.compile(
    r'messages\.\w+\s*\(request,\s*f["\']([^"\']+)["\']'
)
BARE_MSG = re.compile(
    r'messages\.\w+\s*\(request,\s*(?!_\()(["\'])([^"\']{4,})\1'
)
HARDCODED_STR_IN_PY = re.compile(
    r'(?:HttpResponse|JsonResponse|render_to_string)\s*\(\s*["\']([^"\']{4,})["\']'
)

def audit_python(fpath):
    rel = fpath.replace(ROOT + os.sep, '')
    with open(fpath, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    for lno, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#'):
            continue

        # f-string messages — can't be wrapped with _()
        for m in FSTRING_MSG.finditer(line):
            text = m.group(1)
            if LOOKS_FRENCH.search(text):
                add(rel, lno, 'FSTR-MSG', text[:100])

        # Bare string messages (not wrapped in _())
        for m in BARE_MSG.finditer(line):
            text = m.group(2)
            if LOOKS_FRENCH.search(text):
                add(rel, lno, 'BARE-MSG', text[:100])

        # Hardcoded return strings (rare)
        for m in HARDCODED_STR_IN_PY.finditer(line):
            text = m.group(1)
            if LOOKS_FRENCH.search(text):
                add(rel, lno, 'HARDCODED-PY', text[:100])

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def run():
    # Templates
    for dirpath, _, files in os.walk(TPL_DIR):
        for fname in files:
            if fname.endswith('.html'):
                audit_template(os.path.join(dirpath, fname))

    # Python files
    for dirpath, _, files in os.walk(CORE_DIR):
        # Skip __pycache__ and migrations
        if '__pycache__' in dirpath or 'migrations' in dirpath:
            continue
        for fname in files:
            if fname.endswith('.py'):
                audit_python(os.path.join(dirpath, fname))

    # Group by file
    by_file = {}
    for fpath, lno, kind, text in issues:
        by_file.setdefault(fpath, []).append((lno, kind, text))

    # Sort and print
    total = 0
    for fpath in sorted(by_file):
        file_issues = sorted(by_file[fpath])
        print(f'\n{"="*70}')
        print(f'  {fpath}  ({len(file_issues)} issues)')
        print(f'{"="*70}')
        for lno, kind, text in file_issues:
            print(f'  L{lno:4d}  [{kind:12s}]  {text}')
            total += 1

    print(f'\n{"="*70}')
    print(f'  TOTAL: {total} issues dans {len(by_file)} fichiers')
    print(f'{"="*70}')

if __name__ == '__main__':
    run()
