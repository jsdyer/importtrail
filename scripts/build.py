#!/usr/bin/env python3
"""Build the Import Trail site offline from checked-in ISED snapshots."""
from datetime import datetime
from html import escape
from pathlib import Path
from string import Template
from tempfile import TemporaryDirectory
from xml.etree import ElementTree
import json
import re
import shutil

from pages import BASE, OGL, embedded, overview, profile, route
from search_metadata import add_search_metadata

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r'[a-z0-9][a-z0-9-]*')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load(root):
    labels = read(root/'config/products.json')
    meta = read(root/'data/editions.json')
    datetime.fromisoformat(meta['checked_at'].replace('Z', '+00:00'))
    if not labels or not meta['years'] or not all(re.fullmatch(r'\d{4}', y) for y in meta['years']):
        raise ValueError('Missing products or dated editions')
    products = {}
    for code, label in labels.items():
        if not re.fullmatch(r'\d{6}',code) or len(label)!=2 or not all(label):
            raise ValueError(f'Invalid configured product {code}')
        item = read(root/'data/products'/f'{code}.json')
        if not item['years'] or set(item['years']) - meta['years'].keys():
            raise ValueError(f'Unknown or empty edition for {code}')
        for year, record in item['years'].items():
            firms = record['firms']
            indexes = [*record['national'], *(i for group in record['origins'].values() for i in group)]
            if not record['description'] or any(len(row)!=3 or not row[0] for row in firms):
                raise ValueError(f'Invalid list for {code} in {year}')
            if any(type(i) != int or not (0 <= i < len(firms)) for i in indexes):
                raise ValueError(f'Unknown importer reference for {code} in {year}')
        products[code] = item
    return products, labels, meta


def build(root=ROOT):
    root = Path(root)
    products, labels, meta = load(root)
    tool = read(root/'tool.json')
    latest = max(meta['years'])
    frame = Template((root/'web/index.html').read_text(encoding='utf-8'))
    dest = root/'dist'
    with TemporaryDirectory(dir=root) as tmp:
        stage = Path(tmp)/'dist'
        stage.mkdir()
        for name in ('style.css','app.mjs','model.mjs','favicon.svg'):
            shutil.copyfile(root/'web'/name,stage/name)
        shutil.copytree(root/'data', stage/'data')
        status = {'checked_at':meta['checked_at'], 'latest_year':int(latest), 'product_count':len(products),
                  'trade_years':[int(y) for y in sorted(meta['years'])],
                  'product_year_count':sum(len(p['years']) for p in products.values())}
        (stage/'data/status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
        urls = []

        def write(path,title,description,body):
            prefix = '../'*path.count('/') or './'
            url = BASE+path
            if path:
                head = f'<link rel="canonical" href="{url}"><meta property="og:url" content="{url}"><meta property="og:title" content="{escape(title)}"><meta property="og:description" content="{escape(description)}"><meta property="og:type" content="website">'
                trail = [{'@type':'ListItem','position':1,'name':'Import Trail','item':BASE},
                         {'@type':'ListItem','position':2,'name':'Product directory','item':BASE+'records/'}]
                if path!='records/':
                    trail.append({'@type':'ListItem','position':3,'name':title,'item':url})
                crumbs = {'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':trail}
                head += f'<script type="application/ld+json">{embedded(crumbs)}</script>'
            else:
                head = ''
            page = frame.substitute(title=escape(title),description=escape(description),root=prefix,body=body,head=head)
            if not path:
                dataset = {'@type':'Dataset','@id':BASE+'#dataset','name':'Selected Canadian Importers Database product lists',
                           'description':tool['description'],'license':OGL,
                           'isBasedOn':[m['catalogue'] for m in meta['years'].values()],
                           'temporalCoverage':min(meta['years'])+'/'+latest,'spatialCoverage':'Canada'}
                page = add_search_metadata(page,tool,category='BusinessApplication',datasets=[dataset])
            target=stage/path
            target.mkdir(parents=True,exist_ok=True)
            (target/'index.html').write_text(page,encoding='utf-8')
            if path:
                urls.append(url)

        write('', 'Find Canadian importers by product, origin or company · Import Trail', tool['description'],
              overview(meta,products,labels,'./'))
        write('records/','Canadian importer reports by product and trade year · Import Trail',
              f'Browse {len(products)} Canadian importer product reports by sector and HS code, including published company and origin lists.',
              overview(meta,products,labels,'../',directory=True))
        for code, product in products.items():
            name = labels[code][0]
            for year, capture in product['years'].items():
                path = route(code, year, max(product['years']))
                desc = (f'ISED’s {year} report for {name.lower()} (HS {code}) contains {len(capture["national"])} published national '
                        f'entries and lists for {len(capture["origins"])} origins. Browse companies and business locations.')
                write(path, f'{name} importers in Canada, {year} (HS {code}) · Import Trail', desc,
                      profile(code,year,product,labels,meta,'../'*path.count('/')))
        sitemap = ElementTree.Element('urlset',xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
        for url in urls:
            ElementTree.SubElement(ElementTree.SubElement(sitemap,'url'),'loc').text=url
        ElementTree.ElementTree(sitemap).write(stage/'sitemap.xml',encoding='utf-8',xml_declaration=True)
        (stage/'.nojekyll').touch()
        # Generate the entire replacement before swapping the previous offline build.
        if dest.exists():
            dest.rename(Path(tmp)/'previous')
        stage.rename(dest)
    return status


if __name__=='__main__':
    result = build()
    print(f'Built {result["product_year_count"]} product-year reports covering {result["product_count"]} HS codes.')
