"""Measure isolated bot-import peak RSS without settings or network calls.

Run with the same interpreter from each checkout's repository root:
  /path/to/.venv/bin/python scripts/measure_import_memory.py
"""

import json
import subprocess
import sys

PROBE = """
import json, resource, sys
import telegram_bot.bot
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
mib = peak / (1024 * 1024 if sys.platform == 'darwin' else 1024)
heavy = ('chromadb', 'onnxruntime', 'matplotlib', 'seaborn', 'scipy', 'pandas')
print(json.dumps({'peak_rss_mib': mib, 'heavy_modules': [
    name for name in heavy if name in sys.modules
]}))
"""

for _ in range(3):
    result = subprocess.run(
        [sys.executable, "-c", PROBE], check=True, capture_output=True, text=True
    )
    print(json.dumps(json.loads(result.stdout)))
