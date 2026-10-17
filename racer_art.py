"""Original object mascots shared by video sprites and browser PNGs.

Names are stable racer IDs. Artwork never changes physics or random draws.
"""
from functools import lru_cache
import math
from PIL import Image, ImageDraw, ImageFilter

_CREW = [
    ('Blacky', 'cat', 'Midnight cat', 'A moonlit mischief-maker with velvet ears.'),
    ('Sunny', 'banana', 'Banana', 'A sunny little curve with a very big grin.'),
    ('Cocoa', 'boba', 'Boba', 'Milk tea, chewy pearls and unshakeable composure.'),
    ('Pine', 'matcha', 'Matcha', 'A tiny cup of green calm in a noisy race.'),
    ('Tango', 'fox', 'Fox', 'Pointy ears, bright cheeks and a curious streak.'),
    ('Ghost', 'ghost', 'Mochi ghost', 'A soft little spirit with a surprised smile.'),
    ('Sky', 'cloud', 'Cloud', 'A pocket-sized cloud with a silver-blue lining.'),
    ('Rosy', 'donut', 'Donut', 'Strawberry icing and a confetti kind of mood.'),
    ('Cherry', 'cherries', 'Cherry duo', 'Two cherries, one stem and twice the attitude.'),
    ('Minty', 'gummy', 'Gummy bear', 'A glossy mint bear with a soft-hearted grin.'),
    ('Grape', 'ufo', 'Jelly UFO', 'A grape jelly pilot in a tiny flying saucer.'),
    ('Coral', 'peach', 'Peach', 'A rosy peach with a leaf that never sits still.'),
    ('Lime', 'frog', 'Frog', 'Wide eyes, round toes and boundless curiosity.'),
    ('Slate', 'bot', 'Mini bot', 'A little metal friend with a glowing blue smile.'),
    ('Amber', 'bee', 'Honey bee', 'Golden stripes and a pair of sugar-glass wings.'),
    ('Ruby', 'dragon', 'Dragon', 'A berry-red dragon with tiny golden horns.'),
]
IDENTITIES = {n: dict(name=n, kind=k, label=l, description=d) for n, k, l, d in _CREW}
STYLES = {n: k for n, k, _, _ in _CREW}
INK = (25, 36, 53, 255)
WHITE = (255, 253, 242, 255)


def _mix(color, target, amount):
    return tuple(round(a+(b-a)*amount) for a, b in zip(color[:3], target[:3]))+(255,)


def _star(cx, cy, radius, inner, points=5):
    return [(cx+(radius if i % 2 == 0 else inner)*math.cos(-math.pi/2+i*math.pi/points),
             cy+(radius if i % 2 == 0 else inner)*math.sin(-math.pi/2+i*math.pi/points)) for i in range(points*2)]


def _path(d, start, curves, fill, outline=INK, width=6):
    """Cubic paths keep organic silhouettes editable and reproducible."""
    pts, p = [start], start
    for segment in curves:
        if len(segment) == 2:
            pts.append(segment)
            p = segment
            continue
        a, b, end = segment[:2], segment[2:4], segment[4:]
        for i in range(1, 21):
            t, u = i/20, 1-i/20
            pts.append((u**3*p[0]+3*u*u*t*a[0]+3*u*t*t*b[0]+t**3*end[0],
                        u**3*p[1]+3*u*u*t*a[1]+3*u*t*t*b[1]+t**3*end[1]))
        p = end
    d.polygon(pts, fill=fill)
    if outline:
        d.line(pts+[pts[0]], fill=outline, width=width, joint='curve')


def _face(d, cx=128, cy=131, scale=1, mood='smile', cheek=(255,155,160,255), dark=False):
    s = scale
    for i, dx in enumerate((-31, 31)):
        x = cx+dx*s
        if mood == 'wink' and i == 1:
            d.line([(x-11*s,cy+2*s),(x,cy-5*s),(x+11*s,cy+2*s)],fill=INK,width=max(3,round(6*s)))
        elif mood == 'sleepy':
            d.arc((x-12*s,cy-13*s,x+12*s,cy+5*s),0,180,fill=INK,width=max(3,round(5*s)))
        else:
            d.ellipse((x-15*s,cy-20*s,x+15*s,cy+20*s),fill=WHITE,outline=INK,width=max(2,round(3*s)))
            d.ellipse((x-7*s,cy-12*s,x+8*s,cy+12*s),fill=INK)
            d.ellipse((x-4*s,cy-10*s,x+2*s,cy-4*s),fill=WHITE)
        d.ellipse((x-16*s,cy+24*s,x+6*s,cy+33*s),fill=cheek)
    mouth = WHITE if dark else INK
    if mood == 'surprised':
        d.ellipse((cx-9*s,cy+24*s,cx+9*s,cy+45*s),fill=mouth)
    elif mood == 'cat':
        d.polygon([(cx-6*s,cy+20*s),(cx+6*s,cy+20*s),(cx,cy+27*s)],fill=cheek)
        d.arc((cx-14*s,cy+19*s,cx,cy+34*s),0,155,fill=mouth,width=max(2,round(4*s)))
        d.arc((cx,cy+19*s,cx+14*s,cy+34*s),25,180,fill=mouth,width=max(2,round(4*s)))
    else:
        d.arc((cx-13*s,cy+17*s,cx+13*s,cy+39*s),0,180,fill=mouth,width=max(3,round(5*s)))


def _draw_mascot(color, name):
    img = Image.new('RGBA',(256,256))
    d = ImageDraw.Draw(img)
    base, light, pale, shade = (*color,255), _mix(color,WHITE,.45), _mix(color,WHITE,.78), _mix(color,INK,.28)
    kind = STYLES.get(name,'gummy')
    if kind == 'cat':
        d.arc((164,138,234,218),260,105,fill=INK,width=24)
        d.arc((164,138,234,218),260,105,fill=light,width=12)
        fur = _mix(color,(92,104,146),.44)
        _path(d,(48,97),[(41,72,39,41,53,28),(84,36,99,61,108,65),(139,57,155,62,163,67),
              (177,44,196,32,207,31),(221,58,214,85,211,104),(239,166,204,220,128,222),(55,222,21,174,48,97)],fur)
        d.polygon([(54,48),(64,88),(89,70)],fill=(205,154,210))
        d.polygon([(199,50),(176,73),(202,88)],fill=(205,154,210))
        d.ellipse((111,68,141,98),fill=(255,226,132))
        d.ellipse((122,62,148,89),fill=fur)
        _face(d,cy=137,mood='cat',dark=True)
        for y in (154,165):
            d.line((38,y-3,61,y),fill=pale,width=3)
            d.line((194,y,217,y-3),fill=pale,width=3)
    elif kind == 'banana':
        _path(d,(99,33),[(71,50,48,91,54,137),(59,195,108,226,154,217),(193,209,221,170,222,127),
              (202,158,174,177,149,162),(114,143,104,93,119,48),(99,33)],base)
        _path(d,(113,43),[(91,88,93,138,119,170),(145,201,178,193,197,176),
              (167,213,119,214,91,177),(64,141,76,79,100,43),(113,43)],light,None)
        d.line((101,43,106,24,121,27),fill=INK,width=12)
        d.line((104,39,109,27,119,29),fill=(128,93,46),width=6)
        d.line((216,139,222,124),fill=INK,width=8)
        _face(d,cx=100,cy=128,scale=.67,mood='wink',cheek=(242,149,75))
        d.arc((67,60,128,166),140,215,fill=WHITE,width=5)
    elif kind == 'boba':
        d.line((143,67,153,22),fill=INK,width=19)
        d.line((143,67,153,22),fill=(246,169,157),width=10)
        _path(d,(61,76),[(195,76),(183,211),(182,226,78,227,76,211),(61,76)],pale)
        _path(d,(73,139),[(187,139),(180,210),(178,219,84,219,83,210),(73,139)],light,None)
        d.rounded_rectangle((49,58,208,86),radius=13,fill=shade,outline=INK,width=6)
        d.line((65,66,190,66),fill=light,width=5)
        for x,y,r in ((93,196,10),(122,205,10),(154,197,12),(174,212,8),(106,219,7)):
            d.ellipse((x-r,y-r,x+r,y+r),fill=shade,outline=INK,width=3)
            d.ellipse((x-r/2,y-r/2,x,y),fill=light)
        _face(d,cy=125,scale=.85,cheek=(221,143,121))
        d.line((79,97,84,173),fill=WHITE,width=5)
    elif kind == 'matcha':
        d.ellipse((166,94,235,177),fill=pale,outline=INK,width=7)
        d.ellipse((181,110,221,160),fill=(0,0,0,0),outline=INK,width=4)
        _path(d,(43,87),[(192,87),(191,188,174,217,119,218),(62,218,43,190,43,87)],pale)
        d.ellipse((43,63,193,111),fill=base,outline=INK,width=6)
        d.arc((56,70,181,101),190,345,fill=light,width=5)
        d.line((64,119,66,179),fill=WHITE,width=5)
        _face(d,cx=116,cy=142,scale=.88,mood='sleepy',cheek=light)
        _path(d,(118,51),[(92,49,95,26,101,22),(123,25,127,39,118,51)],light,INK,4)
        d.line((106,33,120,55),fill=INK,width=3)
    elif kind == 'fox':
        _path(d,(43,119),[(37,78,34,35,48,27),(81,39,95,60,105,72),(127,65,147,69,157,76),
              (179,42,203,31,214,34),(222,73,211,103,210,122),(230,164,175,204,129,225),(84,206,23,165,43,119)],base)
        d.polygon([(49,47),(59,102),(87,80)],fill=shade)
        d.polygon([(205,53),(179,82),(202,100)],fill=shade)
        _path(d,(47,137),[(77,135,100,152,128,170),(153,149,181,134,211,137),
              (197,179,153,210,129,218),(88,200,60,174,47,137)],(255,236,198),None)
        _face(d,cy=132,scale=.91,mood='cat',cheek=(248,167,121))
        d.polygon([(119,166),(137,166),(128,176)],fill=INK)
        d.line((70,104,86,92),fill=light,width=5)
    elif kind == 'ghost':
        _path(d,(47,126),[(47,68,77,36,125,36),(175,36,206,70,206,126),(205,169,215,197,224,211),
              (205,226,190,225,178,211),(160,235,142,229,130,216),(113,235,93,228,83,212),
              (64,225,44,225,32,211),(44,184,47,158,47,126)],pale)
        _path(d,(191,112),[(201,169,204,191,217,210),(199,220,191,219,178,208),
              (171,215,168,221,157,221),(177,186,189,153,191,112)],_mix(color,(134,143,194),.3),None)
        d.arc((61,48,165,158),186,262,fill=WHITE,width=7)
        _face(d,cy=127,mood='surprised',cheek=(212,176,221))
    elif kind == 'cloud':
        _path(d,(48,121),[(32,81,72,60,96,76),(100,20,173,23,181,77),(219,64,239,101,217,128),
              (249,149,226,200,189,195),(169,216,141,213,126,202),(107,221,77,212,66,197),(18,207,5,142,48,121)],pale)
        d.arc((61,54,181,170),212,283,fill=WHITE,width=9)
        d.arc((35,122,208,201),11,156,fill=light,width=13)
        _face(d,cy=135,scale=.93,cheek=light)
        d.polygon(_star(211,67,15,6,4),fill=(255,218,110),outline=INK,width=3)
    elif kind == 'donut':
        d.ellipse((28,29,229,229),fill=(220,153,84),outline=INK,width=7)
        d.ellipse((38,36,220,213),fill=(255,209,139))
        _path(d,(44,100),[(50,53,82,37,127,39),(174,35,211,61,214,105),(205,116,219,133,204,145),
              (188,152,205,174,187,185),(173,195,165,179,149,192),(127,210,119,191,102,198),
              (85,203,85,182,67,184),(48,182,57,159,45,147),(29,129,48,115,44,100)],base,shade,4)
        d.ellipse((94,88,163,160),fill=(182,112,63),outline=INK,width=5)
        d.ellipse((103,96,154,151),fill=(0,0,0,0))
        for x in (88,169):
            d.ellipse((x-10,74,x+10,101),fill=INK)
            d.ellipse((x-4,77,x+1,84),fill=WHITE)
        d.arc((116,65,142,88),0,180,fill=INK,width=5)
        for x,y,dx,dy,fill in ((71,124,9,5,WHITE),(180,123,3,10,(154,236,206)),
                (78,164,8,-7,(255,222,99)),(137,176,10,3,WHITE),(172,166,8,6,(156,221,251)),(114,54,10,2,(255,222,99))):
            d.line((x,y,x+dx,y+dy),fill=fill,width=5)
        d.arc((43,48,128,154),192,255,fill=light,width=6)
    elif kind == 'cherries':
        d.line((81,113,112,74,140,33,172,125),fill=INK,width=12)
        d.line((81,113,112,74,140,33,172,125),fill=(86,142,76),width=6)
        _path(d,(140,43),[(158,12,192,22,209,35),(186,60,155,57,140,43)],(134,186,93),INK,5)
        d.ellipse((22,93,139,214),fill=shade,outline=INK,width=6)
        d.ellipse((116,102,237,225),fill=base,outline=INK,width=6)
        d.arc((34,104,103,174),190,267,fill=light,width=7)
        d.arc((128,113,200,187),190,265,fill=light,width=7)
        _face(d,cx=79,cy=149,scale=.54,mood='wink',dark=True)
        _face(d,cx=177,cy=157,scale=.55,dark=True)
    elif kind == 'gummy':
        d.ellipse((43,36,104,99),fill=base,outline=INK,width=6)
        d.ellipse((152,36,213,99),fill=base,outline=INK,width=6)
        d.ellipse((58,51,89,81),fill=light)
        d.ellipse((167,51,198,81),fill=light)
        _path(d,(59,121),[(32,115,23,157,49,168),(41,192,51,221,77,221),(96,221,106,210,111,203),
              (144,203),(153,219,180,230,199,210),(210,197,211,180,204,168),(234,148,221,117,198,121),
              (207,77,174,60,128,60),(84,60,49,79,59,121)],base)
        d.ellipse((88,159,166,203),fill=light)
        d.arc((64,73,143,161),186,264,fill=pale,width=7)
        d.ellipse((59,186,80,204),fill=light)
        d.ellipse((177,186,198,204),fill=light)
        _face(d,cy=120,scale=.86,mood='cat',cheek=pale)
    elif kind == 'ufo':
        d.ellipse((54,45,204,200),fill=light,outline=INK,width=6)
        _path(d,(67,141),[(71,103,94,82,128,85),(168,82,188,113,190,147),(174,162,83,163,67,141)],base,None)
        d.arc((67,55,160,159),186,267,fill=WHITE,width=7)
        _face(d,cy=115,scale=.76,cheek=pale)
        d.ellipse((21,147,236,215),fill=shade,outline=INK,width=6)
        d.ellipse((21,133,236,191),fill=pale,outline=INK,width=6)
        d.arc((45,140,210,177),0,180,fill=light,width=10)
        for x in (57,103,150,196):
            d.ellipse((x-6,167,x+6,179),fill=base,outline=INK,width=2)
    elif kind == 'peach':
        _path(d,(128,76),[(71,36,30,75,31,128),(31,175,79,212,128,230),
              (177,211,225,174,225,127),(226,72,181,37,128,76)],base)
        d.arc((91,74,151,225),270,70,fill=shade,width=4)
        _path(d,(122,68),[(128,26,171,19,198,37),(184,69,147,82,122,68)],(111,179,103),INK,5)
        d.line((130,62,178,39),fill=(59,117,77),width=4)
        d.arc((44,73,113,167),187,269,fill=pale,width=7)
        _face(d,cy=134,scale=.97,mood='wink',cheek=light)
    elif kind == 'frog':
        d.ellipse((38,167,100,226),fill=shade,outline=INK,width=6)
        d.ellipse((157,167,219,226),fill=shade,outline=INK,width=6)
        d.ellipse((33,68,224,213),fill=base,outline=INK,width=6)
        for x in (78,178):
            d.ellipse((x-38,37,x+38,119),fill=base,outline=INK,width=6)
            d.ellipse((x-23,52,x+23,107),fill=WHITE)
            d.ellipse((x-9,65,x+12,94),fill=INK)
            d.ellipse((x-3,67,x+3,74),fill=WHITE)
        d.ellipse((70,141,187,201),fill=pale)
        d.arc((81,112,176,164),0,180,fill=INK,width=6)
        d.ellipse((52,127,80,140),fill=(247,172,138))
        d.ellipse((177,127,205,140),fill=(247,172,138))
        for x in (65,180):
            d.line((x,202,x-5,215),fill=light,width=4)
            d.line((x+12,204,x+12,217),fill=light,width=4)
    elif kind == 'bot':
        d.line((128,59,128,28),fill=INK,width=8)
        d.ellipse((117,18,139,40),fill=(161,230,237),outline=INK,width=5)
        d.rounded_rectangle((26,99,58,162),radius=12,fill=shade,outline=INK,width=6)
        d.rounded_rectangle((198,99,230,162),radius=12,fill=shade,outline=INK,width=6)
        d.rounded_rectangle((48,55,208,215),radius=36,fill=light,outline=INK,width=7)
        d.rounded_rectangle((61,83,195,166),radius=23,fill=INK)
        for x in (96,161):
            d.rounded_rectangle((x-10,106,x+10,137),radius=9,fill=(154,240,233))
            d.rectangle((x-6,109,x-2,115),fill=WHITE)
        d.line((116,147,128,153,140,147),fill=(154,240,233),width=5)
        d.line((70,71,156,71),fill=pale,width=5)
        for x in (99,127,155):
            d.ellipse((x-5,184,x+5,194),fill=shade)
        d.rounded_rectangle((67,209,98,229),radius=8,fill=shade,outline=INK,width=4)
        d.rounded_rectangle((159,209,190,229),radius=8,fill=shade,outline=INK,width=4)
    elif kind == 'bee':
        d.ellipse((24,51,110,139),fill=(220,244,244),outline=INK,width=6)
        d.ellipse((146,51,232,139),fill=(220,244,244),outline=INK,width=6)
        d.arc((37,64,92,119),180,280,fill=WHITE,width=6)
        d.arc((159,64,214,119),180,280,fill=WHITE,width=6)
        d.polygon([(113,212),(128,237),(143,212)],fill=INK)
        d.ellipse((61,74,195,222),fill=base,outline=INK,width=6)
        d.arc((60,107,196,184),0,180,fill=INK,width=14)
        d.arc((68,147,188,215),0,180,fill=INK,width=13)
        for x,end in ((99,83),(157,172)):
            d.line((x,88,end,52),fill=INK,width=6)
            d.ellipse((end-7,43,end+7,57),fill=base,outline=INK,width=3)
        _face(d,cy=117,scale=.72,cheek=light)
    elif kind == 'dragon':
        _path(d,(62,149),[(21,149,14,102,31,79),(48,86,60,97,77,120),(62,149)],shade)
        _path(d,(194,149),[(235,149,242,102,225,79),(208,86,196,97,179,120),(194,149)],shade)
        d.line((30,93,53,131),fill=light,width=5)
        d.line((225,93,202,131),fill=light,width=5)
        d.polygon([(67,79),(70,22),(102,68)],fill=(255,218,133),outline=INK,width=5)
        d.polygon([(154,68),(186,22),(189,79)],fill=(255,218,133),outline=INK,width=5)
        d.rounded_rectangle((53,61,203,217),radius=57,fill=base,outline=INK,width=6)
        d.rounded_rectangle((62,144,194,211),radius=32,fill=light,outline=INK,width=4)
        _face(d,cy=122,scale=.8,cheek=pale)
        for x in (100,156):
            d.ellipse((x-4,167,x+4,174),fill=shade)
        d.polygon([(118,63),(128,42),(138,63)],fill=(255,218,133),outline=INK,width=3)
        d.arc((69,76,142,151),185,260,fill=light,width=6)
    return img


@lru_cache(maxsize=512)
def _portrait(color, size, armed, name):
    mascot = _draw_mascot(color,name)
    shadow = Image.new('RGBA',mascot.size,(7,15,28,0))
    shadow.putalpha(mascot.getchannel('A').filter(ImageFilter.GaussianBlur(2)).point(lambda a: round(a*.20)))
    img = Image.new('RGBA',mascot.size)
    img.alpha_composite(shadow,(0,4))
    img.alpha_composite(mascot)
    if armed:
        d = ImageDraw.Draw(img)
        d.ellipse((184,12,248,76),fill=INK,outline=WHITE,width=3)
        d.polygon(_star(216,44,24,11),fill=(255,207,65,255))
    return img.resize((size,size),Image.Resampling.LANCZOS)


def make_portrait(color, size=90, armed=False, name=''):
    return _portrait(tuple(color),int(size),bool(armed),name).copy()
