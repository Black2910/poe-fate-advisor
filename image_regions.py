"""Determine selectable TOP Fate row from parchment title plates, not screen history.

Local Pillow-only geometry, no game reads, no OCR, no network, no API.  The
crop ends BELOW reward icons but ABOVE collected Fates, despite the PoE dialog
moving up/down with number of cards.  Ambiguous geometry is explicitly flagged.
"""
from __future__ import annotations
from dataclasses import dataclass
from PIL import Image, ImageFilter
import math

@dataclass(frozen=True)
class FateImageRegions:
    title: Image.Image
    offered: Image.Image
    offered_bounds: tuple[int, int, int, int]
    full_size: tuple[int, int]
    cards_count: int | None = None
    geometry_card_boxes: tuple[tuple[int,int,int,int],...] = ()
    geometry_confident: bool = False


def _plate_rectangles(image: Image.Image):
    """Find tan card title plates; all coordinates in image pixels."""
    sample = image.convert('RGB')
    scale = min(1., 670 / max(sample.width, 1))
    sample = sample.resize((max(1,round(sample.width*scale)),max(1,round(sample.height*scale))))
    w,h = sample.size
    src=sample.load(); mask=Image.new('L',(w,h)); px=mask.load()
    for y in range(int(h*.86)):
        for x in range(w):
            r,g,b=src[x,y]
            if r>g+16 and g>b+8 and 94<r<244 and g>65 and b>30:
                px[x,y]=255
    closed=mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    v=closed.tobytes(); visited=bytearray(len(v)); components=[]
    for start in range(len(v)):
        if visited[start] or v[start]<128: continue
        visited[start]=1; stack=[start]; xa=w; xb=0; ya=h; yb=0; area=0
        while stack:
            k=stack.pop(); y,x=divmod(k,w)
            xa=min(xa,x); xb=max(xb,x); ya=min(ya,y); yb=max(yb,y); area+=1
            for p in (k-1,k+1,k-w,k+w):
                if (p<0 or p>=len(v) or (p==k-1 and x==0)
                    or (p==k+1 and x==w-1) or visited[p] or v[p]<128):
                    continue
                visited[p]=1; stack.append(p)
        bw=xb-xa+1; bh=yb-ya+1
        if (w*.075<bw<w*.30 and 11<bh<max(65,h*.18)
            and area>max(360,w*h*.0017)):
            components.append((xa,ya,bw,bh,area))
    return [(round(x/scale),round(y/scale),round(ww/scale),round(hh/scale),area)
            for x,y,ww,hh,area in components]


def _top_plates(image: Image.Image) -> list[tuple[int,int,int,int]]:
    comps = sorted(_plate_rectangles(image), key=lambda c:(c[1],c[0]))
    if not comps: return []
    groups=[]
    for c in comps:
        cy=c[1]+c[3]/2
        matched=next((g for g in groups if abs(g[0]-cy)<max(34,image.height*.055)), None)
        if matched is None: groups.append([cy,[c]])
        else: matched[1].append(c)
    # The topmost row can contain 1 to 3 offers; the bottom row is history.
    groups.sort(key=lambda g:g[0])
    # Ignore a lone ornamental header plate when a later 2/3-card row exists.
    candidates=[]
    for cy, row in groups:
        dedup=[]
        for c in sorted(row,key=lambda p:p[0]):
            if dedup and c[0] < dedup[-1][0]+dedup[-1][2]*.55:
                if c[4]>dedup[-1][4]: dedup[-1]=c
            else: dedup.append(c)
        if 1<=len(dedup)<=3:
            candidates.append(dedup)
    selected=candidates[0] if candidates else None
    if selected and len(selected)==1 and len(candidates)>1:
        # Ignore a single, very WIDE ornamental title plate (the word
        # "Fates"); don't confuse it with a genuine single offered card.
        rest=candidates[1]
        median_width=sorted(c[2] for c in rest)[len(rest)//2]
        if selected[0][2]>median_width*1.45:
            selected=rest
    return [(x,y,w,h) for x,y,w,h,_ in selected] if selected else []


def fate_image_regions(image: Image.Image) -> FateImageRegions:
    w,h=image.size
    if w<=0 or h<=0: raise ValueError('Ungültige Screenshotgröße')
    full_screen=w/h>=1.45
    # A generous probe window: detect parchment titles even when Fate dialog
    # is shifted far down, rather than cropping out their reward icons.
    probe=(int(w*(.19 if full_screen else .03)), int(h*.06),
           int(w*(.82 if full_screen else .97)), int(h*.80))
    src=image.crop(probe)
    plates=_top_plates(src)
    if plates:
        absplates=[(x+probe[0],y+probe[1],pw,ph) for x,y,pw,ph in plates]
        # approx 350px from title to bottom icon at native 2048x1151.
        card_height=int(h*.35)
        title_y=min(p[1] for p in absplates)
        left=max(0, min(p[0] for p in absplates)-int(w*.035))
        right=min(w, max(p[0]+p[2] for p in absplates)+int(w*.035))
        top=max(0,title_y-int(h*.012))
        bottom=min(h,title_y+card_height)
        # For some layouts the window is extremely close to the lower history
        # row. Clip before its title if another plate row is detected.
        allplates=_plate_rectangles(src)
        history_y=[p[1]+probe[1] for p in allplates
                   if p[1]+probe[1]>title_y+int(h*.30)]
        if history_y:
            bottom=min(bottom,min(history_y)-int(h*.018))
        bottom=max(bottom,top+int(h*.25))
        header_top=max(0,title_y-int(h*.14))
        header_bottom=max(header_top+25,title_y-int(h*.030))
        header=(max(0,int(w*.40)),header_top,min(w,int(w*.60)),header_bottom)
        # Full card rough bounds as independent local geometry. Use only for
        # plausibility checks; AI must still read visible names.
        cardboxes=tuple((max(0,x-int(w*.012)),max(0,y-int(h*.008)),
                         min(w,x+cw+int(w*.012)),min(h,y+card_height))
                        for x,y,cw,ch in absplates)
        bounds=(left,top,right,bottom)
        return FateImageRegions(image.crop(header),image.crop(bounds),bounds,(w,h),
                                len(plates),cardboxes,True)
    # Fallback for alternate UI themes / Boss altar without cards; do not
    # claim independently verified number of offers.
    offered_bounds=(int(w*.20),int(h*.08),int(w*.80),int(h*.72)) if full_screen else (
        int(w*.025),int(h*.01),int(w*.975),int(h*.80))
    header_bounds=(int(w*.40),0,int(w*.60),int(h*.23)) if full_screen else (int(w*.3),0,int(w*.7),int(h*.23))
    return FateImageRegions(image.crop(header_bounds),image.crop(offered_bounds),
                            offered_bounds,(w,h),None,(),False)


def to_full_image_boxes(result:dict, view:FateImageRegions) -> dict:
    """Map chosen card box in the offered crop back to original screenshot."""
    xa,ya,xb,yb=view.offered_bounds; fw,fh=view.full_size
    cw,ch=xb-xa,yb-ya
    for card in result.get('cards',[]):
        if not isinstance(card,dict): continue
        b=card.get('box')
        if not (isinstance(b,list) and len(b)==4 and
                all(isinstance(v,(int,float)) and not isinstance(v,bool)
                    and math.isfinite(v) for v in b)):
            card['box']=None; continue
        x0,y0,x1,y1=map(float,b)
        if not (0<=x0<x1<=1000 and 0<=y0<y1<=1000):
            card['box']=None; continue
        card['box']=[round((xa+x0*cw/1000)*1000/fw,3),
                     round((ya+y0*ch/1000)*1000/fh,3),
                     round((xa+x1*cw/1000)*1000/fw,3),
                     round((ya+y1*ch/1000)*1000/fh,3)]
    return result
