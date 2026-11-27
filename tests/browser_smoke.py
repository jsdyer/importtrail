"""Test first visits, local search and static edition pages at desktop and phone widths."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import tempfile
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass


def main():
    data=ROOT/'data/products'
    coffee=json.loads((data/'090111.json').read_text())['years']
    year=max(coffee)
    national=coffee[year]['national']
    listing=coffee[year]['firms'][national[0]] if national else coffee[year]['firms'][0]
    origin=next(iter(coffee[year]['origins']),None)
    prior=min(coffee)
    shots=ROOT/'browser-checks'
    shots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        (Path(temp)/'importtrail').symlink_to(ROOT/'dist',target_is_directory=True)
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=temp))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}/importtrail/'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None)
                errors=[]
                for width, height, js in [(1280,850,True),(390,844,True),(320,640,True),(320,640,False)]:
                    ctx=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=js)
                    page=ctx.new_page()
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(base)
                    assert page.get_by_role('heading',level=1).inner_text()=='Who imports goods into Canada?'
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    variant='interactive' if js else 'static'
                    page.screenshot(path=str(shots/f'home-{width}-{variant}.png'))
                    if js:
                        search=page.get_by_role('searchbox',name='Search listings')
                        search.wait_for(state='visible')
                        box=search.bounding_box()
                        assert 0 <= box['y'] and box['y'] + box['height'] <= height, (width,height,box)
                        search.fill('nothing-matches-xyz')
                        assert page.locator('.product:visible').count()==0
                        search.fill(listing[0])
                        assert page.locator('[data-code="090111"]').is_visible()
                        page.get_by_role('button',name='Clear filters').click()
                        page.get_by_label('Sector').select_option('Electronics')
                        assert page.locator('[data-code="847130"]').is_visible()
                        assert not page.locator('[data-code="090111"]').is_visible()
                        page.get_by_role('button',name='Clear filters').click()
                    else:
                        assert not page.locator('#catalog-filter').is_visible()
                    page.locator('[data-code="090111"]').click()
                    assert 'green coffee' in page.locator('h1').inner_text().lower()
                    if national:
                        assert page.locator('#national').get_by_text(listing[0],exact=True).count()>0
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    if js and national:
                        name_filter=page.get_by_role('searchbox',name='Find a listed name or city')
                        name_filter.fill(listing[0])
                        assert page.locator('#national tbody tr:visible').count()>0
                        name_filter.fill('no-such-company-xyz')
                        assert page.locator('#national tbody tr:visible').count()==0
                    if origin:
                        group=page.locator('details').filter(has=page.locator('summary',has_text=origin)).first
                        group.locator('summary').click()
                        assert group.locator('li').first.is_visible()
                    page.get_by_role('link',name=prior,exact=True).click()
                    assert f'/{prior}/' in page.url and prior in page.locator('.years strong').inner_text()
                    assert 'Canadian importers' in page.locator('h1').inner_text()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    ctx.close()
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()

if __name__=='__main__':
    main()
