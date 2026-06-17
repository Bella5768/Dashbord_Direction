"""
Internationalisation automatique — wraps gettext_lazy/_() sur les strings.
Usage: python scripts/apply_i18n.py [--dry-run]
"""
import re, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY  = '--dry-run' in sys.argv


def write(path, content):
    if DRY:
        print(f'  [dry] would write {path}')
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)


# ─────────────────────────────────────────────────────────────────────
# models.py  –  gettext_lazy sur choices + verbose_name
# ─────────────────────────────────────────────────────────────────────

def patch_models(src):
    changes = 0

    # 1. Import gettext_lazy
    if 'gettext_lazy' not in src:
        src = src.replace(
            'from django.db import models',
            'from django.db import models\nfrom django.utils.translation import gettext_lazy as _',
            1,
        )
        changes += 1

    # 2. Choice labels  ('slug', 'Label')  or  ("slug", "Label")
    #    Only inside _CHOICES lists — after a line ending with = [
    #    We wrap the second element if it isn't already _('...')
    def _wrap_choice(m):
        nonlocal changes
        q1, key, q2, label, q3 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if label.startswith('_('):
            return m.group(0)
        changes += 1
        return f"({q1}{key}{q1}, _('{label}'))"

    # Match:  ('slug',  'Label')  or  ("slug",  "Label")
    # * instead of + to allow empty key strings like ('', 'En attente')
    src = re.sub(
        r"\((['\"])([^'\"]*)\1,\s*'([^']+)'\)",
        lambda m: f"('{m.group(2)}', _('{m.group(3)}'))" if not m.group(3).startswith('_(') else m.group(0),
        src,
    )
    src = re.sub(
        r'\((["\'])([^"\']*)\1,\s*"([^"]+)"\)',
        lambda m: f'("{m.group(2)}", _("{m.group(3)}"))' if not m.group(3).startswith('_(') else m.group(0),
        src,
    )

    # 3. verbose_name="..." / verbose_name='...'
    def _wrap_vn(m):
        nonlocal changes
        q, val = m.group(1), m.group(2)
        if val.startswith('_('):
            return m.group(0)
        changes += 1
        return f'verbose_name=_({q}{val}{q})'

    src = re.sub(
        r"verbose_name=(['\"])([^'\"]+)\1",
        _wrap_vn,
        src,
    )

    # 4. verbose_name_plural
    def _wrap_vnp(m):
        nonlocal changes
        q, val = m.group(1), m.group(2)
        if val.startswith('_('):
            return m.group(0)
        changes += 1
        return f'verbose_name_plural=_({q}{val}{q})'

    src = re.sub(
        r"verbose_name_plural=(['\"])([^'\"]+)\1",
        _wrap_vnp,
        src,
    )

    return src, changes


# ─────────────────────────────────────────────────────────────────────
# views / decorators  –  gettext on messages.*(request, 'str')
# Skip f-strings entirely.
# ─────────────────────────────────────────────────────────────────────

def patch_views(src, fname):
    changes = 0

    # 1. Import
    needs_import = 'gettext as _' not in src and 'ugettext as _' not in src
    if needs_import:
        # Insert before first 'from django' import
        src = re.sub(
            r'^(from django\.)',
            r'from django.utils.translation import gettext as _\n\1',
            src,
            count=1,
            flags=re.MULTILINE,
        )
        changes += 1

    # 2. Simple-quoted messages (not f-strings)
    def _wrap_simple_q(m):
        nonlocal changes
        func, text = m.group(1), m.group(2)
        if text.startswith("_("):
            return m.group(0)
        changes += 1
        return f"messages.{func}(request, _('{text}'))"

    def _wrap_simple_dq(m):
        nonlocal changes
        func, text = m.group(1), m.group(2)
        if text.startswith('_('):
            return m.group(0)
        changes += 1
        return f'messages.{func}(request, _("{text}"))'

    # messages.success(request, 'text')  — single quote, no f-prefix
    src = re.sub(
        r"messages\.(success|error|warning|info)\(request,\s*'([^']+)'\)",
        _wrap_simple_q,
        src,
    )
    # messages.success(request, "text")  — double quote, no f-prefix
    src = re.sub(
        r'messages\.(success|error|warning|info)\(request,\s*"([^"]+)"\)',
        _wrap_simple_dq,
        src,
    )

    return src, changes


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────

def process(relpath, fn):
    full = os.path.join(ROOT, relpath)
    with open(full, encoding='utf-8') as f:
        src = f.read()
    new, n = fn(src, relpath)
    if new != src:
        write(full, new)
        print(f'  OK  {relpath}  ({n} changements)')
    else:
        print(f'     {relpath}  -- rien a changer')


if __name__ == '__main__':
    print('=== models.py ===')
    full = os.path.join(ROOT, 'core/models.py')
    with open(full, encoding='utf-8') as f:
        src = f.read()
    new, n = patch_models(src)
    if new != src:
        write(full, new)
        print(f'  OK  core/models.py  ({n} marqueurs)')
    else:
        print('  -- rien a changer')

    print('\n=== views / decorators ===')
    for v in ['core/views.py', 'core/views_leave.py', 'core/views_roles.py', 'core/decorators.py']:
        process(v, patch_views)

    print('\nFait. Lancez extract_messages.py pour régénérer le .po.')
