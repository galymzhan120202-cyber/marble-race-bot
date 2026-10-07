"""Rebuild the browser portraits from the same artist code as video sprites."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from race_sim import RACER_POOL
from racer_art import make_portrait

output = root / 'assets' / 'racers'
output.mkdir(parents=True, exist_ok=True)
for racer in RACER_POOL:
    make_portrait(racer['color'], 256, name=racer['name']).save(output / (racer['name'].lower()+'.png'))
print(f'Built {len(RACER_POOL)} portraits in {output}')
