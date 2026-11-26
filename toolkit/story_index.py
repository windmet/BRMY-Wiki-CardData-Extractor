"""Build the community story ledger from a master snapshot, subtitle data and saved BWIKI HTML."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .core.session import MasterDataSession
from .domains.story_catalog import extract
from .domains.story_cast import GARBAGE_SPEAKERS, card_relation, card_series


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def build(master, station, wiki, checked):
    from bs4 import BeautifulSoup

    session = MasterDataSession.open(master)
    tables = session.tables
    source = extract(session)
    cards = tables.by_id('mst_character_card', 'CharacterCardId')
    people = tables.by_id('mst_character', 'CharacterId')
    events = tables.by_id('mst_event', 'EventId')
    threads = tables.by_id('mst_main_story', 'MainStoryThreadNo')
    names = {''.join(row['CharacterNameJpn'].split()): key for key, row in people.items()}
    playable = {key for key, row in people.items()
                if ((row.get('CharacterGroupCode') != 99) if row.get('CharacterGroupCode') is not None else (key <= 21))}
    stories, episodes, aliases, ep_availability = {}, {}, {}, {}
    catalog = [['story_id','剧情类型','日文名称','中文名称','系列','角色归属ID','活动ID','卡牌ID','活动形式码','索引日期','年份','原表话数','熟肉索引状态','主线关联','内部时间线','活动形式','有轴话数','原始分类','日期依据']]
    chapters = [['story_id','episode_id','话序','日文标题','原始日期','来源表','字幕轴入口']]
    cast = [['story_id','episode_id','角色ID','剧本署名','身份','出场依据','字幕轴入口','首条操作序号','署名台词数']]
    related = [['story_id','关系','对象ID','来源']]
    gaps = [['对象','待核事项','依据']]
    labels = dict(main='主线',character='个人',event='活动',card='卡牌',campaign='其他',login='其他')
    for section in source['Sections']:
        kind, key, raw = section['Kind'], section['Key'], section['Raw']
        table = section['SourceTable']
        if kind == 'puzzle' or 'from_other_story_type' in table:
            continue
        parent = next(iter(section['Parents']), {})
        first = key[0]
        sid = '-'.join([kind,*map(str,key[:-1])]); eid = f'{sid}-{key[-1]}'
        person = first if kind == 'character' else cards.get(first, {}).get('CharacterId') if kind == 'card' else None
        series = ''; title = parent.get('TitleName',''); event = events.get(first,{}) if kind == 'event' else {}
        date = raw.get('ReleaseDateTime') or raw.get('StartTime') or parent.get('ReleaseDateTime','')
        if kind == 'main':
            thread = threads[first]; series = ('Interlude ' if thread['MainStoryTypeCode']==2 else 'Thread ') + thread['TitleName']
            title = title or series
        elif kind == 'card':
            title = cards[first]['CharacterCardName']; date = date or cards[first].get('ReleaseDateTime','')
        elif kind == 'character' and not title:
            title = people[first]['CharacterNameJpn'] + f' / 第{key[1]}章'
        elif kind == 'event':
            title = event.get('EventTitle',''); series = next((word for word in ('Prequel','Travelogue','Vignette') if title.casefold().startswith(word.casefold())), '')
        elif kind == 'campaign':
            title = parent.get('CampaignTitle','')
        elif kind == 'login':
            title = re.sub(r'\s*\[\d+日目\]$', '',section['Title'])
        stories.setdefault(sid,[sid,labels[kind],title,'',series,person, first if event else '',first if kind=='card' else '',event.get('EventFormat','')])
        episodes[eid] = [sid,eid,key[-1],section['Title'],date,table,'']
        ep_availability[eid] = section['Availability']['Status']
    for link in source['CrossStoryLinks']:
        if 'from_other_story_type' not in link['SourceTable']:
            continue
        alias = 'prequel-'+'-'.join(map(str,link['SourceKey']))
        if link['Status']=='resolved':
            target = 'event-'+'-'.join(map(str,link['TargetKey'])); aliases[alias] = target
            stories[episodes[target][0]][4] = 'Prequel'
        else:
            gaps.append([alias,link['Status'],link['SourceTable']])
    for table in ('mst_event_a','mst_event_b','mst_event_c','mst_event_accumulate_item'):
        for row in tables.rows(table,active_only=True):
            for field in ('CharacterCardIds','PickUpCharacterCardIds','PickUpCharacterCardId'):
                values = row.get(field) or []
                for number in values if isinstance(values,list) else [values]:
                    if f'card-{number}' in stories:
                        related.append([f'card-{number}','活动关联卡',row['EventId'],f'{table}.{field}'])
    index = read(station/'index.json')
    station_entries = []
    for category in index['categories']:
        for group in category['groups']:
            for item in group['episodes']:
                entry = item['id']; eid = aliases.get(entry,entry); episode = episodes[eid]
                episode[-1] = ','.join(filter(None,[episode[-1],entry]))
                station_entries.append((entry, eid, episode))
    for entry, eid, episode in station_entries:
        entrances = episode[-1].split(',')
        preferred = eid if eid in entrances else entrances[0]
        if entry != preferred:
            continue
        counts, positions = Counter(), {}
        for pos, op in enumerate(read(station/'ep'/f'{entry}.json'),1):
            if op[0]=='c' and op[1].strip():
                speaker = op[1].strip()
                if speaker in GARBAGE_SPEAKERS:
                    continue
                counts[speaker] += 1; positions.setdefault(speaker,pos)
        for name, count in counts.items():
            person = names.get(''.join(name.split()))
            identity = '角色' if person in playable else 'NPC角色' if person else '玩家' if '<Self' in name else '未归一署名'
            cast.append([episode[0],eid,person,name,identity,'发言',entry,positions[name],count])
    resources = [['resource_id','类型','平台','BV','分P','原始链接','链接状态','视频最后核验']]
    links = [['resource_id','story_id','范围提示','来源表头','UP主（原行）','进度（原行）','匹配依据','来源页读取日期']]
    known = {}; matched = set(); soup = BeautifulSoup(wiki.read_bytes(),'html.parser',from_encoding='utf-8')
    wiki_tables = soup.select('.mw-parser-output table'); event_names = defaultdict(list)
    for sid,row in stories.items():
        if row[1]=='活动': event_names[row[2]].append(sid)
    for table in wiki_tables:
        header = table.select_one('tr'); is_event = header and '活动名' in header.get_text(); heading = table.find_previous(['h2','h3','h4'])
        for tr in table.select('tr'):
            cells = tr.find_all('td',recursive=False)
            if len(cells)<3: continue
            category = cells[0].get_text(strip=True)
            if not is_event and category not in ('主线','个人','卡牌'): continue
            anchor = cells[1].find('a'); title = anchor.get('title','') if anchor else cells[1].get_text(strip=True)
            card = re.fullmatch(r'Card (\d+)',title); targets = []
            if category=='卡牌' and card and 'card-'+card[1] in stories: targets = ['card-'+card[1]]
            if is_event and len(event_names[title])==1: targets = event_names[title]
            if category=='个人':
                owners = {int(match[1]) for ref in table.select('a[title]') if (match:=re.fullmatch(r'Card (\d+)',ref['title'])) and int(match[1]) in cards}
                people_ids = {cards[number]['CharacterId'] for number in owners}
                candidates = [sid for sid,row in stories.items() if row[1]=='个人' and row[5] in people_ids]
                if len(people_ids)==1 and len(candidates)==1: targets = candidates
            for ref in cells[2].select('a[href]'):
                url = ref['href']; bv = re.search(r'BV[0-9A-Za-z]{10}',url); parsed = urlparse(url)
                if not parsed.netloc or parsed.scheme not in ('http','https'): continue
                if not bv and parsed.path.rstrip('/')=='/video':
                    gaps.append([ref.get_text(strip=True),'无有效资源定位',url]); continue
                part = parse_qs(parsed.query).get('p',[''])[0]; rid = bv[0]+(':'+part if part else '') if bv else 'url-'+hashlib.sha256(url.encode()).hexdigest()[:16]
                if rid not in known:
                    known[rid]=True; resources.append([rid,'视频熟肉' if bv else '待核资源','Bilibili' if bv else parsed.netloc,bv[0] if bv else '',part,url,'待核验',''])
                hint = str(ref.previous_sibling or '').strip() if isinstance(ref.previous_sibling,str) else ''
                if category=='主线':
                    scope = {'Thread 0～Interlude Ⅰ:':('Thread 0','Thread 1','Interlude I'), 'Thread 2：':('Thread 2',)}.get(hint,())
                    targets = [key for key,val in stories.items() if val[1]=='主线' and val[4] in scope]
                for sid in targets or ['']:
                    links.append([rid,sid,hint or title,heading.get_text(strip=True) if heading else '',cells[3].get_text(' / ',strip=True) if len(cells)>3 else '',cells[4].get_text(' / ',strip=True) if len(cells)>4 else '',('卡牌ID' if card else '活动同名' if is_event else '合集标注范围' if category=='主线' else '角色栏唯一篇章') if sid else '待核对',checked]); matched.add(sid)
                if not targets: gaps.append([rid,'待对齐剧情',hint or title or category])
    if not resources[1:]: raise ValueError('BWIKI snapshot has no recognized resources')
    grouped = defaultdict(list)
    for episode in episodes.values(): grouped[episode[0]].append(episode)
    memberships = defaultdict(set)
    origins = defaultdict(set)
    for sid, _, number, _ in related[1:]:
        memberships[sid].add(number)
    for relation in related[1:]:
        sid, _, number, _ = relation
        event = events[number]; start = event.get('OpenStartTime') or event.get('StartTime') or ''
        earlier = any((other_start := events[other].get('OpenStartTime') or events[other].get('StartTime')) and other_start < start for other in memberships[sid])
        release = (cards[stories[sid][7]].get('ReleaseDateTime') or '')[:10]
        relation[1] = card_relation(event, '' if release.startswith(('2001-','3001-','9999-')) else release, earlier)
        if relation[1] == '首发活动候选': origins[sid].add(number)
    for sid, row in stories.items():
        items = grouped[sid]; dates = sorted(item[4] for item in items if item[4] and not item[4].startswith(('2001-','3001-','9999-')))
        date = dates[0] if dates else ''; basis = '原表' if date else ''; original = row[1]
        if original == '卡牌':
            row[4] = card_series(row[2])
            if len(origins[sid]) == 1:
                number = next(iter(origins[sid])); event = events[number]; row[6] = number
                row[4] = row[4] or event['EventTitle']
                if not date and (opening := event.get('OpenStartTime')) and not opening.startswith(('2001-','3001-','9999-')):
                    date, basis = opening, '关联活动开放日（推定）'
        elif original in ('活动','其他') and 'anniversary' in row[2].casefold():
            row[1] = '周年活动'
        row.extend([date,date[:4],len(items),'已索引·范围待核' if sid in matched else '待补录','未核实','','部门箱活（banner）' if original=='活动' and row[4] in ('Prequel','Travelogue') else '',sum(bool(item[-1]) for item in items),original,basis]); catalog.append(row)
        if sid not in matched: gaps.append([sid,'未对齐资源','不等于没有翻译'])
    chapters.extend(episodes.values())
    for item in episodes.values():
        if not item[-1] and ep_availability.get(item[1]) not in ('unreleased_placeholder', 'upcoming'):
            gaps.append([item[1], '无字幕轴入口', item[5]])
    stats = Counter((row[1],row[12]) for row in catalog[1:])
    return {'剧情总表':catalog,'章节':chapters,'出场证据':cast,'熟肉资源':resources,'资源关联':links,'活动卡关联':related,'待核清单':gaps,'分类统计':[['剧情类型','索引状态','篇数'],*[[*key,count] for key,count in sorted(stats.items())]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('master','station','wiki','out'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--wiki-date',required=True); args = parser.parse_args()
    data = build(args.master,args.station,args.wiki,args.wiki_date); args.out.mkdir(parents=True,exist_ok=True)
    for name,rows in data.items():
        with (args.out/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as stream: csv.writer(stream).writerows(rows)
    (args.out/'story-index.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')


if __name__=='__main__': main()
