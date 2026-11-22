"""A single image sheet with current cards plus magnified reward icons.

The screenshot is acquired only once by the user's F8.  The sheet is sent in
ONE OpenAI response request: no separate name-verification call required.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps

ASSETS=Path(__file__).resolve().parent/'assets'


def _font(size):
    for path in ('C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).exists():
            try: return ImageFont.truetype(path,size)
            except OSError: pass
    return ImageFont.load_default()


def create_visual_sheet(view, *, with_reference=True):
    """All screenshot pixels come from the ONE upper-offered row, never history."""
    header=view.title.convert('RGB'); offered=view.offered.convert('RGB')
    W=1440
    frame=ImageOps.contain(offered,(W,660),Image.Resampling.LANCZOS)
    # Reward icons are located below the card art, and can be near the bottom
    # when the dialog shifts down. Zoom full LOWER HALF to avoid missing them.
    icon_part=offered.crop((0,int(offered.height*.48),offered.width,offered.height))
    zoom=ImageOps.contain(icon_part,(W,410),Image.Resampling.LANCZOS)
    pad=18; header_height=130
    footer_height=110 if with_reference else 15
    H=header_height+frame.height+55+zoom.height+footer_height
    canvas=Image.new('RGB',(max(frame.width,zoom.width,header.width)+2*pad,H),'#10151a')
    d=ImageDraw.Draw(canvas)
    titlefont=_font(22); labelfont=_font(18)
    d.text((pad,8),'SPIELFENSTER-TITEL  /  CURRENT SCREEN',fill='#faf8e6',font=titlefont)
    # The original Fates/Invoke Fates title is kept as an unaltered crop.
    header.thumbnail((W,68),Image.Resampling.LANCZOS)
    canvas.paste(header,(pad,38))
    y=header_height
    d.text((pad,y-25),'A: OBERE AUSWAHL – LINKS NACH RECHTS',fill='#b0eacf',font=labelfont)
    canvas.paste(frame,(pad,y))
    y+=frame.height+36
    d.text((pad,y-28),'B: GLEICHE KARTEN, UNTERE HAELFTE VERGROESSERT – LOOT-ICONS',fill='#b0eacf',font=labelfont)
    canvas.paste(zoom,(pad,y))
    y+=zoom.height+9
    if with_reference:
        d.text((pad,y),'Bestaetigte Referenzbeispiele: Icons, NICHT Fate-Namen',fill='#ece7dd',font=labelfont)
        for i,(fn,label) in enumerate((('currency_example.png','Currency / Waehrung'),
                                       ('rare_armour_example.png','RareArmour / Ruestung'))):
            imfile=ASSETS/fn
            if imfile.is_file():
                icon=Image.open(imfile).convert('RGB').resize((68,68),Image.Resampling.LANCZOS)
                x=pad+i*330;canvas.paste(icon,(x,y+24));d.text((x+78,y+45),label,fill='#ffffff',font=_font(15))
    return canvas
