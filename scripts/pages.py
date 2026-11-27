"""Build readable, linkable result pages from the two separate ISED importer lists."""
from collections import defaultdict
from html import escape
import json

BASE = 'https://coolcode.ca/importtrail/'
FAQ = 'https://ised-isde.canada.ca/site/ised/en/canadian-importers-database/frequently-asked-questions'
OGL = 'https://open.canada.ca/en/open-government-licence-canada'
REPORT = 'https://www.ised-isde.canada.ca/app/ixb/cid-bdic/productReport.html?hsCode='
MAPLE = 'https://coolcode.ca/maplelabel/records/quebec-cheese-and-coffee/'
EXPORT = 'https://coolcode.ca/exportneighbours/'


def embedded(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')


def link(url, label):
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def route(code, year, latest):
    path = f'records/hs-{code}/'
    return path if year == latest else path + year + '/'


def section(title, contents, anchor=''):
    identifier = f' id="{anchor}"' if anchor else ''
    return f'<section class="section"{identifier}><div class="wrap"><h2>{title}</h2>{contents}</div></section>'


def date_text(checked_at):
    return checked_at[:10]


def product_card(code, labels, capture, root):
    name, sector = labels
    return (f'<a class="product" data-code="{code}" data-sector="{escape(sector)}" href="{root}records/hs-{code}/">'
            f'<span class="code">HS {code}</span><b>{escape(name)}</b>'
            f'<span class="meta">{len(capture["national"]):,} national entries · {len(capture["origins"]):,} published origins</span></a>')


def catalogue(products, labels, root):
    groups = defaultdict(list)
    fields = {}
    for code in sorted(products, key=lambda k: labels[k][0]):
        item = products[code]['years']
        year = max(item)
        capture = item[year]
        name, sector = labels[code]
        groups[sector].append(product_card(code, labels[code], capture, root))
        fields[code] = [' '.join([code, name, sector, year, capture['description']]),
                        *capture['origins'], *(' '.join(firm) for firm in capture['firms'])]
    grouped = ''.join(f'<section class="group"><h3>{escape(s)}</h3><div class="grid">{"".join(groups[s])}</div></section>' for s in sorted(groups))
    return f'{grouped}<script type="application/json" id="catalog-fields">{embedded(fields)}</script>'


def search_form(labels):
    sectors = sorted({sector for _, sector in labels.values()})
    options = ''.join(f'<option>{escape(sector)}</option>' for sector in sectors)
    return f'''<form class="filters" id="catalog-filter" hidden>
<label>Search listings<input type="search" name="q" placeholder="Try coffee, Burnaby or 090111"></label>
<label class="compact">Sector<select name="sector"><option value="">All sectors</option>{options}</select></label>
<button type="button">Clear filters</button></form><p id="search-status" class="status" role="status"></p>'''


def overview(meta, products, labels, root, directory=False):
    latest = max(meta['years'])
    count = len(products)
    body = catalogue(products, labels, root)
    form = search_form(labels)
    if directory:
        return (f'<section class="hero"><div class="wrap"><p class="eyebrow">Import Trail · Product directory</p>'
                f'<h1>Canadian importer reports by product</h1><p>Explore {count} selected goods from the Canadian Importers Database. '
                f'The latest trade year is {latest}.</p></div></section>' + section('Find a product', form + body, 'products'))
    code = '090111'
    example = ''
    if code in products:
        year = max(products[code]['years'])
        capture = products[code]['years'][year]
        bands = [b for b in capture.get('concentration', []) if b[0] is not None]
        if bands:
            count_firms, value, share = bands[-1]
            example = f'''<aside class="sample"><small>Inside one product · Green coffee beans · {year}</small>
<strong class="number">{share:g}% of import value</strong><div class="bar" aria-hidden="true"><i style="width:{share:g}%"></i></div>
<p>ISED attributes this share to a group of {count_firms} major importers.</p>
{link(root + route(code,year,year), 'Explore the green coffee report →')}</aside>'''
    hero = f'''<section class="hero"><div class="wrap intro"><div><p class="eyebrow">Canadian Importers Database · Trade year {latest}</p>
<h1>Who imports goods into Canada?</h1><p>Search by product, importer, city, origin or HS code to find companies listed in Canadian customs records.</p>
{form}
<p>{link('#products', 'Browse the '+str(count)+' products ↓')}</p></div>{example}</div></section>'''
    years = ' · '.join(link(meta['years'][y]['catalogue'], y+' source edition') for y in sorted(meta['years'],reverse=True))
    notes = f'''<div class="notes"><p>Innovation, Science and Economic Development Canada (ISED) publishes annual lists of major importers using customs records. The national product list and the product-and-origin lists have separate coverage. Companies may include brokers and non-resident importers.</p>
<p>The source check runs monthly. Latest trade year <b>{latest}</b>. Last successful source check <time>{date_text(meta['checked_at'])}</time>.</p>
<p>{years} · {link(FAQ, 'ISED methodology')} · {link(OGL, 'Open Government Licence – Canada')}</p>
<p>Use {link(EXPORT, 'Export Neighbours')} to explore Canadian exports, or {link(MAPLE, 'Maple Label’s Québec coffee and cheese examples')} to read Canadian-origin claims on retail packaging.</p>
<p>Search filters run in your browser. The current filter appears in the page address for sharing.</p></div>'''
    return hero + section('Product reports', body, 'products') + section('Sources and coverage', notes, 'sources')


def address(firm):
    return ', '.join(part for part in firm[1:] if part) or 'Location not supplied'


def national_table(capture):
    refs = capture['national']
    if not refs:
        return '<p>ISED’s national workbook contains no published entries for this product and year. Check the available product-and-origin lists below.</p>'
    rows = ''.join(f'<tr><td>{escape(capture["firms"][i][0])}</td> <td>{escape(address(capture["firms"][i]))}</td></tr>' for i in refs)
    return f'''<p>The national workbook lists these importers across all origins. The location is the published business address.</p>
<form class="filters" id="firms-filter" hidden><label>Find a listed name or city<input type="search" name="name" placeholder="Filter national entries"></label><button type="button">Clear</button></form>
<p class="status" role="status" id="firms-status"></p><table class="comp"><caption>{len(refs):,} published national entries, in name order</caption>
<thead><tr><th scope="col">Importer</th><th scope="col">Business location</th></tr></thead><tbody>{rows}</tbody></table>'''


def origin_lists(capture):
    groups = []
    for country, indexes in capture['origins'].items():
        firms = [capture['firms'][i] for i in indexes]
        entries = ''.join(f'<li>{escape(firm[0])}<span class="meta">{escape(address(firm))}</span></li>' for firm in firms)
        plural = 'entry' if len(firms) == 1 else 'entries'
        groups.append(f'<details class="origin"><summary>{escape(country)} · {len(firms):,} {plural}</summary><ul>{entries}</ul></details>')
    if not groups:
        return '<p>ISED’s product-and-origin workbook has no published listings for this product and year.</p>'
    return (f'<p>Choose an origin to see the companies ISED lists for this exact product and origin. '
            'Confidentiality rules limit which lists are published. A company can appear in several lists.</p>'
            f'<div class="origins">{"".join(groups)}</div>')


def concentration_table(bands):
    if not bands:
        return ''
    body = ''
    for count, value, pct in bands:
        label = 'All importers' if count is None else f'Top {count}'
        body += f'<tr><td>{label}</td><td>${value:,}</td><td>{pct:g}%</td></tr>'
    return section('How much do the largest importers account for?', f'''<p>ISED groups importers by import value.
Each row includes the groups above it. Individual company values are confidential.</p>
<table class="comp"><caption>Cumulative national market concentration</caption>
<thead><tr><th scope="col">Importer group</th><th scope="col">Canadian dollars</th><th scope="col">Share of import value</th></tr></thead>
<tbody>{body}</tbody></table>''', 'concentration')


def profile(code, year, product, labels, meta, root):
    name, sector = labels[code]
    years = product['years']
    latest = max(years)
    capture = years[year]
    national, origins = len(capture['national']), len(capture['origins'])
    switch = ' '.join(f'<strong aria-current="page">{y}</strong>' if y == year else link(root+route(code,y,latest), y) for y in sorted(years,reverse=True))
    bands = capture.get('concentration', [])
    classification = 'ISED product description' if capture.get('description_source','ISED') == 'ISED' else 'Product classification'
    hero = f'''<section class="hero"><div class="wrap"><p class="eyebrow">{escape(sector)} · HS {code} · Trade year {year}</p>
<h1>Canadian importers of {escape(name.lower())}</h1><p>{classification} · {escape(capture['description'])}</p>
<div class="summary"><div class="metric"><b>{national:,}</b>Published national entries</div>
<div class="metric"><b>{origins:,}</b>Origins with published lists</div></div>
<nav class="years" aria-label="Trade year"><span>Trade year</span>{switch}</nav><p class="links">
{link('#national','National importer list')} {link('#origins','Browse by origin')} {link('#concentration','Import values and shares') if bands else ''}</p></div></section>'''
    receipt = meta['years'][year]
    sources = [link(receipt['catalogue'], 'ISED '+year+' data catalogue')]
    sources.extend(link(u, name+' workbook') for name,u in receipt['files'].items())
    sources += [link(REPORT+code,'Latest ISED product report'),link(root+'data/products/'+code+'.json','Download this product’s saved editions (JSON)')]
    source_list = '<ul class="source-list">'+''.join('<li>'+s+'</li>' for s in sources)+'</ul>'
    context = [link(root+'records/','All Canadian importer reports')]
    context += [link(root+'records/hs-'+c+'/', n) for c,(n,s) in labels.items() if s==sector and c!=code][:4]
    if code.startswith('0901') or code=='851671':
        context.append(link(MAPLE, 'Maple Label · Québec coffee and cheese claims'))
    context.append(link(EXPORT, 'Export Neighbours · Canadian export markets'))
    notes = (f'<p>The lists use Canadian customs records. Importers can include customs brokers and businesses based abroad. '
             f'ISED identifies major importers covering up to 80% of import value, subject to its disclosure rules. '
             f'An importer’s address and the product’s country of origin describe different things. '
             f'{link(FAQ,"Read ISED’s methodology")}.</p><p>Trade year {year}. Edition workbooks checked {date_text(receipt.get("checked_at",meta["checked_at"]))}. '
             f'Contains information licensed under the {link(OGL,"Open Government Licence – Canada")}.</p>')
    return (hero + concentration_table(bands) + section('National importer list',national_table(capture),'national')
            + section('Importers by country of origin',origin_lists(capture),'origins') + section('Sources and downloads',notes+source_list,'sources')
            + section('Explore more', '<div class="links">'+' '.join(context)+'</div>'))
