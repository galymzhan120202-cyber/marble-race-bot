"""Original, code-drawn racer portraits shared by videos and browser assets."""
from functools import lru_cache
import math

from PIL import Image, ImageDraw

# Each racer has a silhouette detail, expression and emblem, independent of
# its colour. Keep these identities when palettes change between arenas.
STYLES = {
    'Blacky': ('mask', 'moon'), 'Sunny': ('smile', 'sun'),
    'Cocoa': ('calm', 'bars'), 'Pine': ('focused', 'leaf'),
    'Tango': ('wink', 'bolt'), 'Ghost': ('ghost', 'ghost'),
    'Sky': ('smile', 'wing'), 'Rosy': ('wink', 'heart'),
    'Cherry': ('focused', 'cherry'), 'Minty': ('calm', 'leaf'),
    'Grape': ('mask', 'diamond'), 'Coral': ('smile', 'shell'),
    'Lime': ('wink', 'chevron'), 'Slate': ('visor', 'bars'),
    'Amber': ('focused', 'sun'), 'Ruby': ('visor', 'diamond'),
}


def _star(cx, cy, radius, inner, points=5):
    return [(cx + (radius if i%2==0 else inner)*math.cos(-math.pi/2+i*math.pi/points),
             cy + (radius if i%2==0 else inner)*math.sin(-math.pi/2+i*math.pi/points))
            for i in range(points*2)]


@lru_cache(maxsize=512)
def _portrait(color, size, armed, name):
    # Draw at a common high resolution; small racing sprites keep smooth,
    # high-contrast faces without changing the physics silhouette.
    img = Image.new('RGBA', (256,256))
    d = ImageDraw.Draw(img)
    ink = (17,25,42,255)
    white = (248,252,255,255)
    light = tuple(round(v+(255-v)*.42) for v in color) + (255,)
    dark = tuple(round(v*.62) for v in color) + (255,)
    mood, emblem = STYLES.get(name, ('smile','star'))
    d.rounded_rectangle((37,48,231,239), radius=46, fill=(0,0,0,65))
    d.rounded_rectangle((27,28,223,225), radius=44, fill=dark, outline=ink, width=9)
    d.rounded_rectangle((35,33,215,209), radius=37, fill=(*color,255))
    d.arc((43,40,205,190), 192, 266, fill=light, width=8)
    d.line((56,208,192,208), fill=dark, width=8)

    # Small forehead crests are simple enough to survive Shorts scaling.
    accent = white if sum(color)<390 else ink
    if emblem in ('sun','star'):
        d.polygon(_star(128,66,20,11,8 if emblem=='sun' else 5), fill=accent)
    elif emblem == 'moon':
        d.ellipse((110,46,145,81),fill=white)
        d.ellipse((122,41,153,72),fill=(*color,255))
    elif emblem == 'bolt':
        d.polygon([(127,45),(111,69),(126,69),(120,86),(145,60),(132,60),(139,45)],fill=accent)
    elif emblem == 'chevron':
        for y in (49,66):
            d.line((111,y,128,y+9,145,y),fill=accent,width=6)
    elif emblem in ('leaf','wing'):
        d.ellipse((110,51,143,76),fill=accent)
        d.line((114,75,145,48),fill=(*color,255),width=4)
        if emblem=='wing':
            d.line((107,69,93,62),fill=accent,width=5)
            d.line((148,69,161,62),fill=accent,width=5)
    elif emblem=='diamond':
        d.polygon([(128,46),(148,63),(128,82),(108,63)],fill=accent)
        d.line((117,62,139,62),fill=(*color,255),width=4)
    elif emblem=='heart':
        d.ellipse((108,50,129,70),fill=accent)
        d.ellipse((127,50,148,70),fill=accent)
        d.polygon([(109,63),(147,63),(128,83)],fill=accent)
    elif emblem=='cherry':
        d.ellipse((105,58,125,78),fill=accent)
        d.ellipse((128,62,148,82),fill=accent)
        d.line((116,60,128,44,138,63),fill=accent,width=4)
    elif emblem=='ghost':
        d.arc((109,43,147,78),180,360,fill=ink,width=7)
    elif emblem=='shell':
        for end in (110,128,146):
            d.line((128,79,end,49),fill=accent,width=5)
    else:
        for x in (111,125,139):
            d.rounded_rectangle((x,51,x+7,79),radius=3,fill=accent)

    if mood in ('mask','visor'):
        d.rounded_rectangle((49,94,204,152),radius=20,fill=ink)
        if mood=='visor':
            d.line((62,105,189,105),fill=light,width=5)
    for i,x in enumerate((88,168)):
        if mood=='wink' and i==1:
            d.line((149,127,164,117,181,127),fill=ink,width=8)
            continue
        d.ellipse((x-22,98,x+22,151),fill=white)
        d.ellipse((x-6,111,x+12,139),fill=ink)
        d.ellipse((x+1,114,x+7,121),fill=white)
        if mood in ('focused','calm'):
            tilt = (1 if i==0 else -1)* (10 if mood=='focused' else 2)
            d.line((x-23,91-tilt/2,x+23,91+tilt/2),fill=ink,width=7)
    if mood=='ghost':
        d.ellipse((115,163,141,193),fill=ink)
    elif mood in ('focused','visor'):
        d.line((111,176,144,172),fill=ink,width=7)
    else:
        d.arc((101,153,155,188),0,180,fill=white if sum(color)<200 else ink,width=7)
        if mood in ('smile','wink'):
            d.ellipse((57,152,77,162),fill=light)
            d.ellipse((179,152,199,162),fill=light)
    if armed:
        d.ellipse((182,20,249,87),fill=ink)
        d.polygon(_star(216,53,26,12),fill=(255,207,65,255))
    return img.resize((size,size),Image.Resampling.LANCZOS)


def make_portrait(color, size=90, armed=False, name=''):
    return _portrait(tuple(color),int(size),bool(armed),name).copy()
