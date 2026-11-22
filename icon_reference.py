"""Independent, conservative bitmap check of randomized Fate reward icons.

Reference imagery comes from two sources:
  * five user-verified example crops bundled with the app
  * PoEDB-hosted GGG reward icons, downloaded ONCE and cached, asynchronously

No extra game screenshots, API calls, hovering, or keyboard inputs.  Unknown
icons stay unknown; category labels are NEVER obtained from Fate names.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image, ImageFilter, ImageOps
import math
import os
import threading
from functools import lru_cache

from reward_catalog import REWARD_ICONS
from icon_database import IconDatabase, DB_PATH

BASE = Path(__file__).resolve().parent / 'assets' / 'verified_icons'
CACHE = Path.home() / '.poe_fate_advisor_icons'
CDN = 'https://cdn.poedb.tw/image/Art/2DArt/UIImages/InGame/Augury/AuguryRewardIcon{}.webp'
_cached_preload = False
_preload_lock = threading.Lock()


@dataclass(frozen=True)
class IconMatch:
    category: str
    similarity: float
    margin: float
    source: str


def _features(image: Image.Image) -> tuple[float, ...]:
    """Compare foreground shape rather than shared blue circular backdrop."""
    im=ImageOps.grayscale(image.convert('RGB').resize((64,64),Image.Resampling.LANCZOS))
    blurred=im.filter(ImageFilter.GaussianBlur(5.0))
    raw=list(im.getdata()); smooth=list(blurred.getdata())
    result=[]
    # Ignore background, outer frame and parchment; compare icon silhouette.
    for y in range(15,49,2):
        for x in range(15,49,2):
            if (x-32)**2+(y-32)**2>17**2: continue
            j=y*64+x
            result.append((raw[j]-smooth[j])*0.90+(raw[j]-106)*0.10)
    return tuple(result)


def _corr(a:tuple[float,...], b:tuple[float,...]) -> float:
    if len(a)!=len(b) or not a: return -1
    am=sum(a)/len(a); bm=sum(b)/len(b)
    ac=[x-am for x in a]; bc=[x-bm for x in b]
    denom=math.sqrt(sum(v*v for v in ac)*sum(v*v for v in bc))
    return sum(x*y for x,y in zip(ac,bc))/denom if denom>1e-9 else -1


@lru_cache(maxsize=4)
def _indexed_database_references(mtime_ns:int):
    try:
        return tuple((cat,p,src) for cat,p,src in IconDatabase().reference_files())
    except (OSError,ValueError):
        return ()


def _reference_files():
    for p in BASE.glob('*.png'):
        category=p.stem.split('_')[0]
        if category in REWARD_ICONS:yield category,p,'bundled'
    if CACHE.is_dir():
        for p in CACHE.glob('*.webp'):
            if p.stem in REWARD_ICONS: yield p.stem,p,'poedb'
    stamp=DB_PATH.stat().st_mtime_ns if DB_PATH.is_file() else 0
    yield from _indexed_database_references(stamp)


@lru_cache(maxsize=4)
def _load_refs(available_files):
    refs=[]
    for category,filename,source in available_files:
        p=Path(filename)
        try:
            with Image.open(p) as img:
                refs.append((category,_features(img),source))
        except (OSError, ValueError):pass
    return refs


def match_icon(icon:Image.Image, min_similarity:float=.66, min_margin:float=.105) -> IconMatch:
    """Only return a label when silhouette and runner-up margin are convincing."""
    features=_features(icon)
    scores={}
    sources={}
    files=tuple(sorted((cat,str(p),src) for cat,p,src in _reference_files()))
    for category,ref,source in _load_refs(files):
        score=_corr(features,ref)
        if score>scores.get(category,-2):
            scores[category]=score; sources[category]=source
    if not scores:return IconMatch('unknown',0,0,'no_references')
    ranked=sorted(scores.items(),key=lambda pair:pair[1],reverse=True)
    best,similarity=ranked[0]
    margin=similarity-(ranked[1][1] if len(ranked)>1 else -1)
    if similarity<min_similarity or margin<min_margin:
        return IconMatch('unknown',round(similarity,3),round(margin,3),'low_confidence')
    return IconMatch(best,round(similarity,3),round(margin,3),sources[best])


def crop_reward_icons(screenshot:Image.Image,view) -> list[Image.Image]:
    """Predict the reward circles using the known geometry of each title plate.

    Measured on 5 user screenshots at 2048x1151; UI offsets may vary if
    Windows display/UI scaling changes. Failure is explicitly nonfatal.
    """
    w,h=screenshot.size
    radius=max(14,round(33*h/1151))
    result=[]
    for left,top,right,bottom in view.geometry_card_boxes:
        cx=round((left+right)/2)
        cy=round(top+(360*h/1151))
        if cx-radius<0 or cy-radius<0 or cx+radius>w or cy+radius>h:
            result.append(Image.new('RGB',(66,66),'black'))
        else:
            result.append(screenshot.crop((cx-radius,cy-radius,cx+radius,cy+radius)))
    return result


def independently_read_icons(screenshot:Image.Image,view) -> list[IconMatch]:
    """Find reward icon circles near each locally measured card's lower edge.

    A quick coarse search followed by 1px refinement tolerates uneven UI
    title-plate detection. Accept only a strong, distinctive silhouette match.
    """
    w,h=screenshot.size
    radius=max(14,round(33*h/1151))
    matches=[]
    for left,top,right,bottom in view.geometry_card_boxes:
        cx=round((left+right)/2)
        cy=round(top+360*h/1151)
        def evaluate(dx,dy):
            x=cx+round(dx*h/1151); y=cy+round(dy*h/1151)
            if x-radius<0 or y-radius<0 or x+radius>w or y+radius>h:return None
            crop=screenshot.crop((x-radius,y-radius,x+radius,y+radius))
            return match_icon(crop,min_similarity=-1,min_margin=-1)
        coarse=[]
        for dy in (-16,-10,-5,0,5,10,16):
            for dx in (-3,0,3):
                result=evaluate(dx,dy)
                if result:coarse.append((result.similarity,dx,dy,result))
        if not coarse:
            matches.append(IconMatch('unknown',0,0,'no_icon_geometry'));continue
        _,coarse_x,coarse_y,_=max(coarse,key=lambda rec:rec[0])
        final=[]
        for dy in range(coarse_y-3,coarse_y+4):
            for dx in range(coarse_x-3,coarse_x+4):
                result=evaluate(dx,dy)
                if result:final.append(result)
        strongest=max(final,key=lambda hit:hit.similarity)
        if strongest.similarity<.78 or strongest.margin<.14:
            matches.append(IconMatch('unknown',strongest.similarity,strongest.margin,'low_confidence'))
        else:
            matches.append(strongest)
    return matches


def _download_one(category:str) -> bool:
    destination=CACHE/(category+'.webp')
    if destination.is_file():return True
    request=Request(CDN.format(category),headers={'User-Agent':'PoE-Fate-Advisor/1.3 (public-icon-cache)'})
    try:
        with urlopen(request,timeout=3) as response:
            data=response.read(120_000)
        from io import BytesIO
        with Image.open(BytesIO(data)) as img:
            img.verify()
        destination.write_bytes(data)
        return True
    except Exception:
        return False


def prefetch_official_icons() -> None:
    """Cache public images; index successful downloads in the local database."""
    try:
        database=IconDatabase()
        database.import_existing_sources()
        CACHE.mkdir(parents=True,exist_ok=True)
        missing=[k for k in REWARD_ICONS if not (CACHE/(k+'.webp')).exists()]
        if missing:
            # Connection failures do not block screenshot analysis.
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(_download_one,missing))
        database.import_existing_sources()
    except Exception:
        return


def start_icon_prefetch() -> None:
    """Perform public reference download away from the user's F8 hot path."""
    if os.getenv('POE_FATE_DISABLE_ICON_DOWNLOAD','').strip()=='1':
        return
    global _cached_preload
    with _preload_lock:
        if _cached_preload:return
        _cached_preload=True
    threading.Thread(target=prefetch_official_icons,daemon=True,name='fate-icon-cache').start()
