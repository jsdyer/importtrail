"""Check the two newest ISED importer editions and retain only validated, dated records."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
import hashlib
import json
import os
import re
import shutil
from workbooks import rows

ROOT = Path(__file__).resolve().parents[1]
SEARCH = 'https://open.canada.ca/data/api/3/action/package_search?'
REPORT = 'https://www.ised-isde.canada.ca/app/ixb/cid-bdic/productReport.html?hsCode='
FILES = ['HS6 Description','Major Importers by HS6','Major Importers by HS6, country']
HOSTS = {'open.canada.ca','ised-isde.canada.ca','www.ised-isde.canada.ca'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')


def download(url, dest):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
        raise ValueError('Unexpected publisher URL')
    with urlopen(Request(url, headers={'User-Agent':'CoolCode Import Trail/1.0 (+https://coolcode.ca/importtrail/)'}), timeout=90) as incoming, dest.open('wb') as out:
        total = 0
        while chunk := incoming.read(1_048_576):
            total += len(chunk)
            if total > 160_000_000:
                raise ValueError('Source exceeds the importer size limit')
            out.write(chunk)
    if total == 0:
        raise ValueError('Empty source')


def packages(path):
    download(SEARCH + urlencode({'q':'title:"Canadian Importers Database"','rows':100}), path)
    results = read_json(path)['result']['results']
    editions = {}
    for d in results:
        match = re.fullmatch(r'Canadian Importers Database \((\d{4})\)', d['title'])
        if not match:
            continue
        editions[match[1]] = d
    if len(editions) < 2:
        raise ValueError('Expected at least two dated releases')
    releases = {}
    for year in sorted(editions)[-2:]:
        d = editions[year]
        if d['license_id'] != 'ca-ogl-lgo':
            raise ValueError('Review changed dataset licence before publication')
        resources = {r['name']:r['url'] for r in d['resources']}
        if set(FILES) - resources.keys():
            raise ValueError(f'Missing HS6 source for {year}')
        releases[year] = {'catalogue':'https://open.canada.ca/data/en/dataset/'+d['id'],
                          'files':{name:resources[name] for name in FILES}}
    return releases


def selected(path, wanted, required):
    source = iter(rows(path))
    headings = [str(s).strip() for s in next(source)]
    if not set(required).issubset(headings):
        raise ValueError(f'Unexpected columns in {path.name}: {headings}')
    positions = [headings.index(h) for h in required]
    id_col = headings.index('HS6-SH6')
    for row in source:
        if not row or len(row) <= id_col:
            continue
        value = row[id_col]
        code = str(int(value)).zfill(6) if isinstance(value, (int,float)) else str(value or '').strip().zfill(6)
        if code in wanted:
            yield code, [str(row[i] or '').strip() if i < len(row) else '' for i in positions]


def extract(paths, year, products):
    labels = dict((code, cols[0]) for code, cols in selected(paths[FILES[0]], products, ['DESCRIPTION_ENG']))
    nationwide = defaultdict(set)
    by_origin = defaultdict(lambda: defaultdict(set))
    fields = ['COMPANY-ENTREPRISE', 'CITY-VILLE', 'PROVINCE_ENG', 'DATA_YEAR-ANNÉE_DES_DONNÉES']
    for idx in (1,2):
        columns = fields if idx == 1 else [*fields, 'COUNTRY']
        for code, values in selected(paths[FILES[idx]], products, columns):
            name,city,region,trade_year = values[:4]
            if not name or int(float(trade_year)) != int(year):
                raise ValueError('Missing name or inconsistent trade year')
            identity = (name, city, region)
            if idx == 1:
                nationwide[code].add(identity)
            elif values[4]:
                by_origin[code][values[4]].add(identity)
            else:
                raise ValueError('Missing origin in product-and-country table')
    if not (labels.keys() & nationwide.keys()) or not by_origin:
        raise ValueError('Source has no matching importer evidence')
    result = {}
    for code in products.keys() & (labels.keys() | nationwide.keys() | by_origin.keys()):
        description = labels.get(code) or products[code][0]
        national = nationwide[code]
        origins = by_origin[code]
        people = sorted(national.union(*origins.values()))
        indexes = {firm:i for i,firm in enumerate(people)}
        result[code] = {'description':description, 'description_source':'ISED' if code in labels else 'Import Trail', 'firms':people, 'national':sorted(indexes[f] for f in national),
                        'origins':{country:sorted(indexes[f] for f in entries) for country, entries in sorted(origins.items())}}
    return result


def concentration(raw, code, expected_year):
    from lxml import html
    page = html.fromstring(raw)
    if code not in page.xpath('string(//h1)'):
        raise ValueError('Unexpected product in official concentration report')
    tables = page.xpath('//table')
    captions = [' '.join(table.xpath('string(caption)').split()) for table in tables]
    year = next((re.search(r' in (\d{4})\b', c) for c in captions if 'Major Canadian importers' in c), None)
    if year is None or year[1] != expected_year:
        raise ValueError(f'Product report for {code} has a different or missing trade year')
    if 'Market concentration' not in captions:
        raise ValueError(f'Concentration table missing for {code}')
    data = []
    for tr in tables[captions.index('Market concentration')].xpath('.//tr[td]'):
        values = [' '.join(c.text_content().split()) for c in tr.xpath('./th | ./td')]
        count, value, share = values
        data.append([None if count=='All' else int(count.replace(',','')), int(value.replace(',','')), float(share.removesuffix('%'))])
    if not data or data[-1][0] is not None or data[-1][2] != 100 or any(not (0 <= r[2] <= 100 and r[1] >= 0) for r in data):
        raise ValueError(f'Invalid concentration figures for {code}')
    return data


def refresh(cache=None):
    products = read_json(ROOT/'config/products.json')
    featured = read_json(ROOT/'config/concentration.json')
    if not all(re.fullmatch(r'\d{6}', k) for k in products) or set(featured) - products.keys():
        raise ValueError('Review the product configuration')
    with TemporaryDirectory(dir=ROOT) as tmp:
        folder = Path(tmp)
        releases = packages(folder/'catalogue.json')
        current = max(releases)
        dest = ROOT/'data'
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        meta = read_json(dest/'editions.json') if (dest/'editions.json').exists() else {'years':{}}
        revised = {}
        for year, receipt in releases.items():
            paths = {}
            for name,url in receipt['files'].items():
                filename = Path(urlsplit(url).path).name
                path = folder/filename
                if cache and (cache/filename).exists():
                    shutil.copyfile(cache/filename,path)
                else:
                    download(url,path)
                paths[name] = path
            result = extract(paths, year, products)
            if year == current and products.keys() - result.keys():
                raise ValueError('Selected product classification changed; review missing codes before updating')
            meta['years'][year] = {**receipt, 'checked_at':stamp, 'sha256':{name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in paths.items()}}
            for code,label in products.items():
                item = revised.setdefault(code, read_json(dest/'products'/f'{code}.json') if (dest/'products'/f'{code}.json').exists() else {'years':{}})
                if code in result:
                    previous = item['years'].get(year, {})
                    item['years'][year] = result[code]
                    if year != current and 'concentration' in previous:
                        item['years'][year]['concentration'] = previous['concentration']
                else:
                    item['years'].pop(year, None)
        def collect(code):
            path = folder/(code+'.html')
            download(REPORT+code,path)
            return code, concentration(path.read_bytes(),code,current)
        with ThreadPoolExecutor(max_workers=2) as pool:
            for code, bands in pool.map(collect, featured):
                revised[code]['years'][current]['concentration'] = bands
        meta['checked_at'] = stamp
        # The workflow publishes only after every source, test and offline build succeeds.
        for code, item in revised.items():
            save(folder/'verified'/f'{code}.json',item)
        save(folder/'verified-meta.json',meta)
        (dest/'products').mkdir(parents=True,exist_ok=True)
        for code in revised:
            os.replace(folder/'verified'/f'{code}.json',dest/'products'/f'{code}.json')
        os.replace(folder/'verified-meta.json',dest/'editions.json')
        print(f'Checked {len(revised)} products across {", ".join(releases)}; latest edition {current}.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-dir', type=Path, help='Use previously downloaded publisher workbooks with their original filenames')
    refresh(parser.parse_args().download_dir)
