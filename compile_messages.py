"""Compile .po files to .mo files without requiring gettext tools.
Uses Django's built-in compilemessages if available, falls back to manual compilation.
"""
import os
import subprocess
import sys


def compile_with_django():
    """Try to compile using Django's management command."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')
    try:
        import django
        django.setup()
        from django.core.management import call_command
        call_command('compilemessages')
        return True
    except Exception as e:
        print(f"Django compilemessages failed: {e}")
        return False


def compile_with_msgfmt():
    """Try to compile using system msgfmt."""
    base = os.path.dirname(os.path.abspath(__file__))
    success = True
    for lang in ['en', 'fr']:
        po = os.path.join(base, 'locale', lang, 'LC_MESSAGES', 'django.po')
        mo = os.path.join(base, 'locale', lang, 'LC_MESSAGES', 'django.mo')
        if os.path.exists(po):
            try:
                subprocess.run(['msgfmt', '-o', mo, po], check=True)
                print(f'{lang}: compiled -> {mo}')
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                print(f'{lang}: msgfmt failed: {e}')
                success = False
    return success


if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base)

    print("Trying Django compilemessages...")
    if not compile_with_django():
        print("Trying system msgfmt...")
        if not compile_with_msgfmt():
            print("ERROR: Could not compile messages. Install gettext tools.")
            print("On Ubuntu/Debian: sudo apt-get install gettext")
            sys.exit(1)

    print("Done!")
