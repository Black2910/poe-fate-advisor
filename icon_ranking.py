"""Deterministic build-aware recommendation from ONE independently cropped image."""
from __future__ import annotations
from fate_engine import DANGER, Fate, FATE_NAMES
from reward_catalog import REWARD_ICONS
from selection_validation import fail_closed_disagreement, position_label, normal_name

ICON_VALUE={
 'Currency':7,'DivineOrb':28,'MirrorShard':35,'FracturingOrb':23,'HinekorasLock':25,
 'AnnulmentOrb':13,'SacredOrb':12,'ReflectiveMist':13,'ExceptionalGems':21,
 'Gems':8,'Viscera':8,'RareRanged':7,'Bow':6,'Quiver':6,'RareArmour':5,
 'Boots':6,'Helmet':5,'BodyArmour':5,'Gloves':5,'RareJewellery':5,
 'Amulet':5,'Ring':5,'Belt':5,'UniqueAuguryItem':17,'UniqueJewel':12,
 'UniqueArmour':9,'UniqueWeapon':7,'UniqueJewellery':10,'UniqueFlask':9,
 'Maps':5,'Gold':3,'Threads':7,'Divination':8,'IncreasedRarityAffectedMonster':5,
}

def icon_score(card, phase, goal):
    k=card.get('reward_icon','unknown')
    if card.get('reward_icon_confidence') not in ('hoch','mittel'): k='unknown'
    points=ICON_VALUE.get(k,1)
    if k in ('RareArmour','RareRanged','Bow','Boots','Gems') and phase=='Kampagne':points+=2
    if k in ('DivineOrb','MirrorShard','FracturingOrb','HinekorasLock','ExceptionalGems') and phase=='Kampagne':points*=.65
    if goal=='Loot':points*=1.65
    if goal=='Sicher':points*=.60
    return points

def score_and_choose(cards:list[dict],prior:list[Fate],phase:str,goal:str) -> tuple[int,str]:
    if not cards: return 0,'Keine angebotenen Karten lesbar.'
    scores=[]
    for card in cards:
        name=card['name'];base_danger=DANGER.get(name,3)
        danger=base_danger*(5.0 if goal=='Sicher' else 3.4)
        rewards=icon_score(card,phase,goal)
        s=rewards-danger
        earlier=[f for f in prior if f.name.casefold()==name.casefold()]
        if len(earlier)==1:
            # First card's reward triples on merge; second is discarded.
            old=earlier[0].rewards.casefold()
            if any(s in old for s in ('currency','währung','divine','mirror','gems')):
                bonus=11
            elif any(s in old for s in ('rüst','armour','bow','bogen','köcher','currency')):
                bonus=6
            else:bonus=3
            s+=bonus*(.65 if goal=='Sicher' else 1)
        elif len(earlier)>1:
            s+=3*(.65 if goal=='Sicher' else 1)
        scores.append(s)
    ix=max(range(len(scores)),key=lambda n:(scores[n],-n))
    card=cards[ix]; pos=position_label(ix+1,len(cards))
    icon=card.get('reward_icon','unknown')
    cat=REWARD_ICONS.get(icon) if card.get('reward_icon_confidence') in ('hoch','mittel') else None
    loot=(f'Icon-Kategorie: {cat} (genaue Variante offen)' if cat else 'Loot-Symbol nicht sicher lesbar')
    dup=sum(p.name.casefold()==card['name'].casefold() for p in prior)
    combo=(f' · {dup} gleiche Fate bereits gesammelt; Kombination beim Boss möglich' if dup else '')
    return ix+1,f'{pos}: {card["name"]}. {loot}. Risiko: {card.get("danger","unklar")}.{combo}'


def validate_geometry(result, view):
    """Independent non-AI parchment card count/bounds. Refuse hallucinated extras."""
    if result.get('screen_type') != 'selection':return result
    cards=result.get('cards',[])
    if not view.geometry_confident or view.cards_count is None:
        return fail_closed_disagreement(result,[], 'Lokale Kartenkonturen nicht sicher erkannt; Screenshotbereich überprüfen.')
    if len(cards)!=view.cards_count:
        return fail_closed_disagreement(result,[],f'KI meldet {len(cards)} Karten, Bildkonturen zeigen {view.cards_count}.')
    names=[c.get('name','') for c in cards]
    # Small differences in whitespace / punctuation should not reject clearly
    # visible card titles. Unknown or invented names remain disallowed.
    canonical={normal_name(n):n for n in FATE_NAMES}
    if not all(isinstance(n,str) and normal_name(n) in canonical for n in names):
        return fail_closed_disagreement(result,[], 'Mindestens ein Fate-Name ist nicht im lokalen Namenkatalog oder unlesbar.')
    for c in cards:
        c['name']=canonical[normal_name(c['name'])]
    names=[c['name'] for c in cards]
    numbers=[c.get('number') for c in cards]
    if numbers != list(range(1,len(cards)+1)):
        return fail_closed_disagreement(result,[], 'Kartennummern inkonsistent.')
    if len(set(names)) != len(names) and len(names)>1:
        # Two identical Fates may be offered; don't forbid duplicates.
        pass
    # Name-read confidence is deliberately INDEPENDENT from the reward icon
    # confidence; one uncertain loot icon must not discard 3 legible titles.
    name_confidence=result.get('names_confidence',result.get('confidence'))
    if name_confidence not in ('hoch','mittel'):
        return fail_closed_disagreement(result,names, 'KI konnte die Kartennamen nicht sicher lesen (Loot-Unsicherheit ist davon getrennt).')
    # Card boxes can be conservatively replaced by locally measured outlines,
    # so a hallucinated box cannot highlight the PREVIOUS card below.
    boxes=view.geometry_card_boxes
    w,h=view.full_size
    for i,(card,box) in enumerate(zip(cards,boxes)):
        x0,y0,x1,y1=box
        card['box']=[round(x0*1000/w,2),round(y0*1000/h,2),
                     round(x1*1000/w,2),round(y1*1000/h,2)]
    result['visual_verification']='geometry_confirmed'
    return result
