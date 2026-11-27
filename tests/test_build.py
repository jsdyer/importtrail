import csv
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'collectors')]
from build import build, load
from pages import BASE, overview, profile, route
from refresh import extract, FILES

class ImportTrailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.status = build()
        cls.products, cls.labels, cls.meta = load(ROOT)
        cls.dist = ROOT/'dist'

    def test_sitemap_contains_only_published_results_with_unique_canonicals(self):
        locs = [n.text for n in ElementTree.parse(self.dist/'sitemap.xml').findall('./{*}url/{*}loc')]
        self.assertEqual(len(locs),self.status['product_year_count']+1)
        self.assertEqual(len(locs),len(set(locs)))
        for url in locs:
            self.assertTrue(url.startswith(BASE+'records/'))
            page=(self.dist/url.removeprefix(BASE)/'index.html').read_text()
            self.assertIn(f'rel="canonical" href="{url}"', page)
            self.assertEqual(page.count('<h1>'),1)
        home=(self.dist/'index.html').read_text()
        self.assertIn('"@type": "Dataset"',home)
        self.assertIn('https://coolcode.ca/maplelabel/records/quebec-cheese-and-coffee/', home)

    def test_green_coffee_evidence_in_static_markup(self):
        record=self.products['090111']['years']['2024']
        page=(self.dist/route('090111','2024',max(self.products['090111']['years']))/'index.html').read_text()
        self.assertEqual(record['concentration'][-1][-1],100.0)
        for count,value,share in record['concentration']:
            self.assertIn(f'{share:g}%', page)
            self.assertIn(f'${value:,}',page)
        national_names=[record['firms'][i][0] for i in record['national']]
        self.assertTrue(national_names)
        self.assertTrue(all(name.replace('&','&amp;') in page for name in national_names))
        self.assertIn('2023', self.products['090111']['years'])
        self.assertIn('Brazil',record['origins'])
        self.assertIn('Maple Label',page)

    def test_company_search_index_and_sensitive_script_escaping(self):
        extra={'999998':{'years':{'2022':{'description':'Token </script>', 'national':[0], 'origins':{}, 'firms':[['Café test','Québec','Québec']]}}}}
        label={'999998':['Example <beans>','Research']}
        meta={'years':{'2022':{'catalogue':'https://example.org','files':{}}},'checked_at':'2023-10-04T00:00:00Z'}
        page=overview(meta,extra,label,'./',directory=True)
        self.assertIn('Example &lt;beans&gt;',page)
        fields=json.loads(re.search(r'id="catalog-fields">(.*?)</script>',page).group(1))
        self.assertIn('Café test Québec Québec', fields['999998'])
        self.assertIn('Token </script>',fields['999998'][0])
        self.assertIn('2022',profile('999998','2022',extra['999998'],label,meta,'../../'))

    def test_origin_evidence_survives_missing_description_and_national_row(self):
        with tempfile.TemporaryDirectory() as temp:
            files = [Path(temp)/f'{i}.csv' for i in range(3)]
            fields = ['HS6-SH6','COMPANY-ENTREPRISE','CITY-VILLE','PROVINCE_ENG','DATA_YEAR-ANNÉE_DES_DONNÉES']
            headers = [['HS6-SH6','DESCRIPTION_ENG'],fields,[*fields,'COUNTRY']]
            records = [[['012345','Official']],
                       [['012345','Alpha','Ottawa','Ontario','2020']],
                       [['012345','Alpha','Ottawa','Ontario','2020','Japan'],['012346','Beta','Toronto','Ontario','2020','Brazil']]]
            for path, header, rows in zip(files,headers,records):
                with path.open('w',newline='') as f:
                    writer=csv.writer(f); writer.writerow(header); writer.writerows(rows)
            result=extract(dict(zip(FILES,files)), '2020',{'012345':['One','Test'],'012346':['Two','Test']})
            self.assertEqual(result['012346']['description_source'],'Import Trail')
            self.assertEqual(result['012346']['national'],[])
            self.assertEqual(result['012346']['origins'],{'Brazil':[0]})
            self.assertEqual(result['012346']['firms'],[('Beta','Toronto','Ontario')])
            self.assertEqual(result['012345']['description_source'],'ISED')

if __name__=='__main__':
    unittest.main()
