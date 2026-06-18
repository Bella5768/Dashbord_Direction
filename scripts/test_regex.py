import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('core/models.py', encoding='utf-8') as f:
    src = f.read()

result = re.sub(
    r"\((['\"])([^'\"]+)\1,\s*'([^']+)'\)",
    lambda m: f"('{m.group(2)}', _('{m.group(3)}'))" if not m.group(3).startswith('_(') else m.group(0),
    src,
)

idx = result.find('STATUS_CHOICES')
print(result[idx:idx+400])
print('---')
idx2 = result.find('TYPE_CHOICES')
print(result[idx2:idx2+300])
