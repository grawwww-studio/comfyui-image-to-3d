# usage (from the repo root, runs laid out as runs/<prefix>_<model>_s<seed>/stills/front.png):
# comparison sheet: python compare_sheet.py <photo.jpg> <prefix> <best_pixal_seed> <best_trellis_seed> <out.png> [view=front] [hr_dir]
# labels language: env SHEET_LANG=en (default) or es
import sys, os
from PIL import Image, ImageDraw, ImageFont
photo, pre, sp, st, out = sys.argv[1:6]; view = sys.argv[6] if len(sys.argv) > 6 else 'front'
S = 720; G = (92, 92, 94)
EN = os.environ.get('SHEET_LANG', 'en') == 'en'
T = ({'in': 'Input photo', 'best': 'best seed, res 1024', 'oth': 'other seed, res 1024', 'x': 'extra run', 'seed': 'seed'} if EN else {'in': 'Foto de entrada', 'best': 'mejor semilla, res 1024', 'oth': 'otra semilla, res 1024', 'x': 'prueba extra', 'seed': 'seed'})
try: FONT = ImageFont.load_default(size=22)
except TypeError: FONT = None
def fit(im):
    im = im.convert('RGB'); r = min(S / im.width, S / im.height); im = im.resize((int(im.width * r), int(im.height * r)))
    c = Image.new('RGB', (S, S), G); c.paste(im, ((S - im.width) // 2, (S - im.height) // 2)); return c
cols = [(T['in'], fit(Image.open(photo)))]
other = {sp: [s for s in ('1234', '777') if s != sp][0], st: [s for s in ('1234', '777') if s != st][0]}
for model, lab, best in (('pixal3d', 'Pixal3D', sp), ('trellis2', 'TRELLIS.2', st)):
    for seed, tag in ((best, T['best']), (other[best], T['oth'])):
        cols.append((f'{lab} seed {seed} ({tag})', fit(Image.open(f'runs/{pre}_{model}_s{seed}/stills/{view}.png'))))
if len(sys.argv) > 7:
    cols.append(('Pixal3D seed %s, res 1536 (%s)' % (sp, T['x']), fit(Image.open(f'{sys.argv[7]}/stills/{view}.png'))))
NC = 3; NR = (len(cols) + NC - 1) // NC
W = Image.new('RGB', (S * NC, (S + 36) * NR), (24, 24, 24)); d = ImageDraw.Draw(W)
for i, (t, im) in enumerate(cols):
    x, y = (i % NC) * S, (i // NC) * (S + 36)
    W.paste(im, (x, y + 36)); d.text((x + 12, y + 10), t, fill=(240, 240, 240), font=FONT)
W.save(out)
