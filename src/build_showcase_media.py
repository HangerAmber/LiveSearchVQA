"""Offline editorial media from archived VQA records; no browser or model calls.

Requires Pillow and ffmpeg on PATH. Optional --paper-figure imports a supplied
illustration, strips metadata, and resizes it for inline reading.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets'
W, H = 1600, 900
BG, INK, MUTED, LINE = '#f7f8f4', '#20313a', '#63747b', '#d9e1dd'
TEAL, BLUE, GOLD, RED = '#357e69', '#507e9c', '#b48247', '#b66669'
COLORS = [BLUE, TEAL, GOLD, '#8a77a4']
RECORDS = json.loads((ROOT/'data/previews/2026-09-05.json').read_text(encoding='utf-8'))
IDS = ['522fc2138b6c-0', 'bfcd16fb2c0f-0', '3c95ec7b092e-0', '9bb125a270d4-0']
ITEMS = [next(it for it in RECORDS if it['id'] == key) for key in IDS]
SHORT = ['When does the main race start?', 'First-half revenue growth?',
         'How much does the sale save?', 'Where is the retirement match?']
LABELS = ['SPORTS / TIME', 'MUSIC / NUMBER', 'RETAIL / NUMBER', 'SPORTS / PLACE']


def font(size, bold=False):
    names = ([Path('C:/Windows/Fonts/segoeuib.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')]
             if bold else [Path('C:/Windows/Fonts/segoeui.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')])
    return ImageFont.truetype(str(next(p for p in names if p.exists())), size)


def txt(d, xy, value, size=24, color=INK, bold=False):
    d.text(xy, str(value), font=font(size, bold), fill=color)


def wrap(d, value, xy, width, size=28, color=INK, bold=False, max_lines=10):
    lines, line = [], ''
    for word in str(value).split():
        trial = (line+' '+word).strip()
        if d.textlength(trial, font=font(size, bold)) > width and line:
            lines.append(line); line = word
        else: line = trial
    if line: lines.append(line)
    if len(lines) > max_lines:
        raise ValueError('Text would overflow its panel')
    for i, line in enumerate(lines):
        txt(d, (xy[0], xy[1]+i*int(size*1.32)), line, size, color, bold)
    return len(lines)*int(size*1.32)


def box(d, rect, fill='white', outline=None):
    d.rounded_rectangle(rect, radius=16, fill=fill, outline=outline, width=2)


def photo(im, item, rect):
    x,y,w,h=rect
    with Image.open(ROOT/'data'/item['image']) as source:
        focal=(0.5,0.12) if item['id']==IDS[3] else (0.5,0.5)
        fitted=ImageOps.fit(source.convert('RGB'), (w,h), method=Image.Resampling.LANCZOS,centering=focal)
    im.paste(fitted,(x,y))


def base(kicker, title, number):
    im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
    txt(d,(56,32),'LiveSearchVQA',24,INK,True)
    txt(d,(1260,36),'ANONYMOUS REVIEW',17,MUTED)
    d.line((56,80,1544,80),fill=LINE,width=2)
    txt(d,(56,110),kicker,19,TEAL,True)
    txt(d,(56,144),title,48,INK,True)
    d.line((56,840,1544,840),fill=LINE,width=2)
    txt(d,(56,857),'ARCHIVED DEMO  /  05 SEP 2026  /  ILLUSTRATED WALKTHROUGH',16,MUTED)
    txt(d,(1420,855),f'{number:02d} / 06',19,MUTED)
    return im,d


def card(im, d, i, x,y,w=430,h=306):
    item=ITEMS[i]; color=COLORS[i]
    box(d,(x,y,x+w,y+h),'white',LINE)
    photo(im,item,(x+10,y+10,w-20,148))
    d.rectangle((x+10,y+156,x+w-10,y+160),fill=color)
    txt(d,(x+18,y+171),LABELS[i],14,color,True)
    wrap(d,SHORT[i],(x+18,y+198),w-36,23,bold=True,max_lines=2)
    ans=item['answer'] if i!=3 else 'Dublin, Ireland'
    txt(d,(x+18,y+246),ans,30,color,True)
    txt(d,(x+18,y+284),item['source']+'  ·  abridged prompt',12,MUTED)


def cover():
    im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
    d.rectangle((0,0,14,H),fill=TEAL)
    txt(d,(56,38),'LIVESEARCHVQA  /  VISUAL WEB SEARCH',20,MUTED,True)
    txt(d,(56,144),'LIVE',94,TEAL,True)
    txt(d,(56,255),'facts.',70,INK,True)
    txt(d,(56,356),'SEARCH',94,BLUE,True)
    txt(d,(56,468),'for evidence.',58,INK,True)
    wrap(d,'A picture tells you what.\nThe web tells you what changed.',(60,583),565,29,max_lines=3)
    for j,(a,b) in enumerate([('01','Visual cue'),('02','Dated fact'),('03','Evidence')]):
        xx=60+j*181
        txt(d,(xx,736),a,18,TEAL,True);txt(d,(xx,764),b,22,INK,True)
    for i in range(4): card(im,d,i,652+(i%2)*446,122+(i//2)*326)
    d.line((56,835,1544,835),fill=LINE,width=2)
    txt(d,(56,852),'Archived cases · 05 Sep 2026 · Questions / long answers abridged for display',17,MUTED)
    return im


def live():
    im,d=base('01 / LIVE','A changing world needs dated questions.',2)
    d.line((115,342,1470,342),fill=LINE,width=5)
    for i,(date,count,label) in enumerate([('15 AUG 2026','200','Archived snapshot'),('18 AUG 2026','171','English-only subset'),('05 SEP 2026','121','Incomplete preview')]):
        x=56+i*510
        d.ellipse((x+204,327,x+232,355),fill=COLORS[i])
        txt(d,(x+108,285),date,26,COLORS[i],True)
        box(d,(x,390,x+466,637),'white',LINE)
        txt(d,(x+30,410),count,68,COLORS[i],True)
        txt(d,(x+30,497),'items',22,MUTED)
        txt(d,(x+30,561),label,27,INK,True)
    box(d,(56,687,1544,805),'#e7efeb')
    txt(d,(87,706),'NEWS → CONSTRUCTION',20,TEAL,True)
    txt(d,(87,748),'48-hour admission window · Explicit builds only · No daily auto-run',30,INK,True)
    return im


def question():
    im,d=base('02 / VISUAL GROUNDING','The image is the clue, not the answer.',3)
    item=ITEMS[1]
    photo(im,item,(56,253,674,436))
    txt(d,(56,714),'Source image: TechCrunch · archived 04 Sep 2026',20,MUTED)
    box(d,(788,253,1544,773),'white',LINE)
    txt(d,(824,282),'IMAGE + QUESTION',19,BLUE,True)
    wrap(d,item['question'],(824,334),679,33,bold=True,max_lines=6)
    d.line((824,615,1505,615),fill=LINE,width=2)
    txt(d,(824,645),'Recognize the medium.',30,INK,True)
    txt(d,(824,698),'Search for the newly reported number.',27,TEAL,True)
    return im


def search():
    im,d=base('03 / SEARCH','Find the right fact, period, and source.',4)
    item=ITEMS[1]
    photo(im,item,(56,244,395,249))
    box(d,(56,520,451,787),'#e7efeb')
    txt(d,(84,547),'GOLD ANSWER',18,TEAL,True)
    txt(d,(82,591),item['answer'],66,TEAL,True)
    txt(d,(84,700),'First-half YoY growth',24,INK,True)
    box(d,(492,244,1544,787),'white',LINE)
    txt(d,(524,273),'ARCHIVED SOURCE EXCERPT / TECHCRUNCH / 04 SEP 2026',18,BLUE,True)
    wrap(d,'“'+item['evidence']+'”',(524,329),980,32,max_lines=5)
    for i,(value,label) in enumerate([('$107.9M','H1 2025 revenue'),('$171.1M','H1 2026 revenue'),('58.6%','YoY increase')]):
        x=524+i*334;fill='#e7efeb' if i==2 else '#f0f2f1'
        box(d,(x,556,x+314,700),fill)
        txt(d,(x+20,577),value,38,TEAL if i==2 else MUTED,True)
        txt(d,(x+20,638),label,22,INK)
    txt(d,(526,730),'Nearby numbers are not interchangeable.',26,TEAL,True)
    return im


def verify():
    trials=ITEMS[1]['certification']['trials']
    cb=[t for t in trials if t['condition']=='closed_book']
    oracle=[t for t in trials if t['condition']=='oracle']
    assert len(cb)==len(oracle)==12
    assert all(t['correct'] is False for t in cb) and all(t['correct'] is True for t in oracle)
    im,d=base('04 / ADMISSION CONTROLS','Fresh does not automatically mean searchable.',5)
    labels=[('P0','Visual cue','Resolve the referent.',BLUE),('P1','No web','12 / 12 incorrect',RED),('P2','Gold evidence','12 / 12 correct',TEAL)]
    for i,(p,name,caption,color) in enumerate(labels):
        x=56+i*509;box(d,(x,264,x+469,662),'white',LINE)
        txt(d,(x+30,285),p,76,color,True)
        txt(d,(x+30,403),name,34,INK,True)
        if i:
            for row in range(3):
                for col in range(4):
                    xx=x+34+col*93; yy=475+row*35
                    if i==1:
                        d.line((xx,yy,xx+15,yy+15),fill=color,width=3);d.line((xx+15,yy,xx,yy+15),fill=color,width=3)
                    else:d.line([(xx,yy+6),(xx+6,yy+13),(xx+19,yy-2)],fill=color,width=3)
        else:
            txt(d,(x+30,482),'Image → referent',29,color,True)
            txt(d,(x+30,533),'Question → new fact',29,color,True)
        txt(d,(x+30,601),caption,27,color,True)
    txt(d,(56,714),'A retained construction item. Not a claim about every model.',32,INK,True)
    txt(d,(56,771),'Recorded 3-model × 4-sample checks · Independent human review remains pending',24,MUTED)
    return im


def end():
    im,d=base('05 / LIVE × SEARCH','See the clue. Find what changed.',6)
    for i in range(4): card(im,d,i,56+i*376,258,w=360,h=310)
    box(d,(56,606,1544,790),'#e7efeb')
    txt(d,(91,633),'Freshness',42,TEAL,True)
    txt(d,(562,633),'Evidence',42,BLUE,True)
    txt(d,(1050,633),'Diagnosis',42,INK,True)
    txt(d,(91,705),'Time-stamped sources',25,INK)
    txt(d,(562,705),'Answer-bearing passages',25,INK)
    txt(d,(1050,705),'No-web / search / oracle',25,INK)
    return im


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--paper-figure',type=Path)
    args=parser.parse_args();OUT.mkdir(exist_ok=True)
    if args.paper_figure:
        with Image.open(args.paper_figure) as image:
            image=ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((2560,2560),Image.Resampling.LANCZOS)
            clean=Image.new('RGB',image.size);clean.paste(image)
            clean.save(OUT/'benchmark-overview.png',optimize=True)
    scenes=[cover(),live(),question(),search(),verify(),end()]
    scenes[0].save(OUT/'showcase-cover.png',optimize=True)
    storyboard=Image.new('RGB',(1600,1040),BG)
    for i,im in enumerate(scenes):
        thumb=im.resize((512,288),Image.Resampling.LANCZOS)
        storyboard.paste(thumb,(16+(i%3)*528,210+(i//3)*340))
    sd=ImageDraw.Draw(storyboard)
    txt(sd,(32,36),'LIVE → SEARCH → VERIFY',54,INK,True)
    txt(sd,(34,113),'An illustrated walkthrough of archived construction records',28,MUTED)
    txt(sd,(34,953),'No new crawl, synthetic search trace, or model leaderboard is implied.',23,MUTED)
    storyboard.save(OUT/'demo-storyboard.png',optimize=True)
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise RuntimeError('ffmpeg must be installed to encode the media')
    with tempfile.TemporaryDirectory(prefix='livesearch-media-') as temp:
        tmp=Path(temp)
        for i,im in enumerate(scenes):
            im.save(tmp/f'scene-{i}.png')
            fade='fade=t=out:st=5.75:d=0.25'
            if i:fade='fade=t=in:st=0:d=0.25,'+fade
            subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-loop','1','-i',str(tmp/f'scene-{i}.png'),'-t','6',
                '-vf',fade,'-r','12','-c:v','libx264','-preset','fast',
                '-crf','20','-pix_fmt','yuv420p','-an',str(tmp/f'part-{i}.mp4')],check=True)
        listing=tmp/'parts.txt'
        listing.write_text(''.join(f"file 'part-{i}.mp4'\n" for i in range(6)),encoding='utf-8')
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),
            '-c','copy','-map_metadata','-1','-movflags','+faststart',str(OUT/'live-search-demo.mp4')],check=True)
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(OUT/'live-search-demo.mp4'),
            '-vf','fps=6,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a',
            '-loop','0',str(OUT/'live-search-demo.gif')],check=True)
    manifest={'edition':'2026-09-25','kind':'illustrated walkthrough, not a screen recording',
        'snapshot':'data/previews/2026-09-05.json','ids':IDS,'display_prompts':'abridged; exact questions remain in JSON',
        'duration_seconds':36,'new_model_calls':0,'agent_search_trajectories_claimed':False,
        'paper_figure':'author-supplied concept illustration; not measured release distribution',
        'outputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*')
                   if p.name in ['showcase-cover.png','benchmark-overview.png','demo-storyboard.png','live-search-demo.mp4','live-search-demo.gif']}}
    (OUT/'showcase-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'outputs':list(manifest['outputs']),'seconds':36,'model_calls':0}))


if __name__=='__main__':main()
