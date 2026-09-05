"""Render a reproducible, illustrated construction walkthrough (no model calls)."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets'
W, H = 1280, 660
INK, MUTED, LINE = '#202d3a', '#647589', '#dce4eb'
BLUE, TEAL, PURPLE, RED = '#3677a5', '#25836d', '#7b65ad', '#c1676b'

def font(size, bold=False):
    names = ([r'C:/Windows/Fonts/segoeuib.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
             if bold else [r'C:/Windows/Fonts/segoeui.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    return ImageFont.truetype(next(p for p in names if Path(p).exists()), size)

def wrap(draw, text, pos, width, size=20, color=INK, bold=False, limit=5):
    f = font(size, bold)
    words, lines, line = text.split(), [], ''
    for word in words:
        trial = (line + ' ' + word).strip()
        if draw.textlength(trial, font=f) > width and line:
            lines.append(line); line = word
        else:
            line = trial
    if line: lines.append(line)
    for i, line in enumerate(lines[:limit]):
        draw.text((pos[0], pos[1] + i * (size + 7)), line, font=f, fill=color)

def tick(draw, x, y, color=TEAL, scale=1):
    draw.line([(x, y+7*scale), (x+6*scale, y+13*scale), (x+19*scale, y)], fill=color, width=max(2,int(3*scale)))

def cross(draw, x, y, color=RED):
    draw.line((x,y,x+15,y+15), fill=color, width=3)
    draw.line((x+15,y,x,y+15), fill=color, width=3)

def render(item, stage, phase):
    canvas = Image.new('RGB', (W,H), '#ffffff')
    d = ImageDraw.Draw(canvas)
    d.text((40,25),'LiveSearchVQA',font=font(32,True),fill=INK)
    d.text((338,36),'From fresh news to an auditable visual question',font=font(21),fill=MUTED)
    d.line((40,79,1240,79),fill=LINE,width=2)
    labels = ['Collect', 'Generate', 'P0 · Ground', 'P1 / P2 · Verify', 'Release']
    for i,label in enumerate(labels):
        x=40+i*244
        fill=TEAL if i==stage else (INK if i<stage else MUTED)
        d.text((x,100),f'{i+1:02d}  {label}',font=font(19,True),fill=fill)
        d.rounded_rectangle((x,136,x+222,140),radius=2,fill=TEAL if i<=stage else LINE)
    d.rounded_rectangle((40,170,470,591),radius=12,fill='#f4f7fa')
    photo=ImageOps.fit(Image.open(ROOT/'data'/item['image']).convert('RGB'),(398,210))
    canvas.paste(photo,(56,186))
    d.text((56,407),'VISUAL REFERENT + NEW FACT',font=font(15,True),fill=BLUE)
    wrap(d,item['question'],(56,437),397,size=19,bold=True,limit=4)
    d.text((56,565),f"Archived demo · {item.get('build_date','2026-08-18')}",font=font(14),fill=MUTED)
    x=514
    if stage==0:
        d.text((x,185),'1. A timestamped source',font=font(29,True),fill=INK)
        d.text((x,239),'English news • source image • article text',font=font(21),fill=MUTED)
        d.rounded_rectangle((x,290,1224,441),radius=9,fill='#eff5fa',outline=LINE,width=2)
        d.text((x+24,312),'PUBLICATION → BUILD',font=font(16,True),fill=BLUE)
        d.line((x+28,385,1179,385),fill=BLUE,width=3)
        d.ellipse((x+22,379,x+34,391),fill=BLUE)
        d.ellipse((1173,379,1185,391),fill=TEAL)
        d.text((x+175,351),'0–48 hours',font=font(26,True),fill=INK)
        d.text((x,492),'Archive the source; keep its timestamp and hash.',font=font(20),fill=MUTED)
    elif stage==1:
        d.text((x,185),'2. Evidence before the question',font=font(29,True),fill=INK)
        d.rounded_rectangle((x,250,1224,396),radius=9,fill='#edf6f2')
        d.text((x+22,269),'VERBATIM SOURCE SPAN',font=font(16,True),fill=TEAL)
        words=item['evidence'].split()
        answer_at=next((j for j,w in enumerate(words) if item['answer'].split()[0] in w),0)
        start=max(0,min(answer_at-10,len(words)-25))
        wrap(d,' '.join(words[start:start+25]),(x+22,307),660,size=20,limit=3)
        d.text((x+20,424),'Evidence',font=font(22,True),fill=TEAL)
        d.text((x+208,424),'→',font=font(24),fill=MUTED)
        d.text((x+261,424),'Image-linked question',font=font(22,True),fill=BLUE)
        d.text((x,500),'Same-call self-check is a heuristic, not P1.',font=font(20),fill=MUTED)
    elif stage==2:
        d.text((x,185),'3. Check the visual link',font=font(29,True),fill=INK)
        rows=['Image matches the source entity / event', 'Image resolves the unnamed referent', 'Answer is not visible in the pixels']
        for j,label in enumerate(rows):
            yy=265+j*87
            d.rounded_rectangle((x,yy,1224,yy+65),radius=7,fill='#f1f6fa')
            tick(d,x+23,yy+21,scale=1.25)
            d.text((x+75,yy+18),label,font=font(21),fill=INK)
        d.text((x,554),'Reject decorative images and image-only questions.',font=font(20),fill=MUTED)
    elif stage==3:
        d.text((x,185),'4. Same item, fresh contexts',font=font(29,True),fill=INK)
        for col,(name,color,bg) in enumerate([('P1 · No web',RED,'#fbf0f0'),('P2 · Gold evidence',TEAL,'#edf6f2')]):
            xx=x+col*365
            d.rounded_rectangle((xx,247,xx+344,512),radius=9,fill=bg)
            d.text((xx+23,265),name,font=font(23,True),fill=color)
            for row in range(3):
                d.text((xx+24,321+row*46),chr(65+row),font=font(18,True),fill=MUTED)
                for column in range(4):
                    px,py=xx+88+column*55,326+row*46
                    cross(d,px,py) if col==0 else tick(d,px,py)
            d.text((xx+23,474),'12 incorrect' if col==0 else '12 correct',font=font(20,True),fill=color)
        d.text((x,548),'One failed condition → reject. Never count API errors.',font=font(20),fill=MUTED)
    else:
        d.text((x,185),'5. Validate, freeze, publish',font=font(29,True),fill=INK)
        for j,(label,value) in enumerate([('TARGET','200 items / requested build'),('PER ITEM','Image + question + source + 24 verdicts'),('VERSION','Date + content hashes + run manifest')]):
            yy=257+j*77
            d.text((x,yy),label,font=font(15,True),fill=TEAL)
            d.text((x,yy+26),value,font=font(23),fill=INK)
        d.rounded_rectangle((x,509,1224,568),radius=8,fill='#edf6f2')
        tick(d,x+22,531,scale=1.2)
        d.text((x+69,523),'Browse cases and switch dated snapshots',font=font(22,True),fill=TEAL)
    d.line((40,609,1240,609),fill=LINE,width=1)
    d.text((40,626),'Illustrated process, not a run recording. P1/P2 are construction-panel-relative.',font=font(15),fill=MUTED)
    d.text((1045,626),'ON DEMAND ONLY',font=font(15,True),fill=TEAL)
    # Slow progress marker: no flashing or implied live API activity.
    end=40+int(1200*(stage+phase)/5)
    d.line((40,654,end,654),fill=TEAL,width=5)
    return canvas

def main():
    OUT.mkdir(exist_ok=True)
    payload=json.loads((ROOT/'data/showcase_cases.json').read_text(encoding='utf-8'))
    if isinstance(payload,dict): payload=payload.get('items',payload.get('questions',[]))
    item=next((i for i in payload if i.get('answer_type')=='numeric'),payload[0])
    frames=[render(item,stage,1) for stage in range(5)]
    frames[-1].save(OUT/'construction-poster.png')
    frames[0].save(OUT/'construction.gif',save_all=True,append_images=frames[1:],
                   duration=3000,loop=0,optimize=True,disposal=1)
    print('Saved illustrated GIF and static poster; no model calls.')

if __name__=='__main__': main()
