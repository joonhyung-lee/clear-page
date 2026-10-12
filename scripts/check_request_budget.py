"""Check request budgets and manual loading in the anonymous host's sandbox.

Run: python scripts/serve.py --port 8773 --anonymous-sandbox
     python scripts/check_request_budget.py
Virtual time covers 16 minutes without waiting for the host's rate window.
No requests are sent to the public service by this check.
"""
import argparse
from collections import Counter
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url',default='http://localhost:8773')
args=parser.parse_args()
BASE=args.base_url.rstrip('/')

def check_page(browser,path,initial_budget):
    page=browser.new_page(viewport={'width':1440,'height':1000})
    requests=[];errors=[];bad=[]
    page.on('request',lambda r: requests.append(r.url) if r.url.startswith('http') else None)
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.on('requestfailed',lambda r: bad.append((r.failure,r.url)))
    page.on('response',lambda r:bad.append((r.status,r.url)) if r.status>=400 else None)
    page.clock.install()
    page.goto(BASE+path,wait_until='networkidle')
    initial=len(requests)
    assert initial<=initial_budget,(path,'initial request count',initial,requests)
    if path=='/':
        page.locator('details').evaluate_all('(nodes)=>nodes.forEach(n=>n.open=true)')
        for selector in ['#embodiment-demo','#controller-pretraining','#mpc-process','#spot-process','#failure-cases']:
            if page.locator(selector).count():
                page.locator(selector).scroll_into_view_if_needed()
                page.wait_for_timeout(800)
        for y in range(0,int(page.evaluate('document.body.scrollHeight')),850):
            page.evaluate('(y)=>scrollTo(0,y)',y);page.wait_for_timeout(70)
        page.locator('#controller-pretraining').scroll_into_view_if_needed()
    else:
        for node in page.locator('[data-flow-node]').all():
            node.click()
            card=page.locator('.component:visible .snippet')
            card.scroll_into_view_if_needed()
            page.wait_for_timeout(250)
            card.locator('.code-line').first.wait_for()
    page.wait_for_timeout(1500)
    before=len(requests)
    page.clock.fast_forward(16*60*1000)
    page.wait_for_timeout(500)
    assert len(requests)==before,('background requests',requests[before:])
    assert not [u for u in requests if ('.mp4' in u and '/teaser-stream.mp4' not in u) or '.hex.js' in u],('automatic media',requests)
    assert not errors,errors
    assert not bad,bad
    assert len(requests)<35,('browse budget',len(requests))
    print(f'PASS {path}: initial={initial}, browse={before}, additional requests over 16 virtual minutes=0',flush=True)
    if path=='/':
        # The opaque-origin sandbox must allow every paper page to render.
        page.locator('[data-resource="paper"]').first.evaluate('(e)=>e.click()')
        frame=page.frame_locator('#resource-dialog iframe')
        frame.locator('#page').wait_for()
        count=int(frame.locator('#position').inner_text().split('/')[-1])
        for index in range(1,count+1):
            assert frame.locator('#position').inner_text()==f'{index} / {count}'
            frame.locator('#page').evaluate('(img)=>img.decode()')
            if index<count:frame.locator('#next').click()
        frame.locator('#previous').click()
        assert frame.locator('#position').inner_text()==f'{count-1} / {count}'
        frame.locator('#page').focus();page.keyboard.press('Escape')
        assert not page.locator('#resource-dialog').evaluate('(d)=>d.open')
        assert not errors,errors
        print(f'PASS sandbox: all {count} paper pages, Previous and Escape',flush=True)
    page.close()

def check_data_retry(browser):
    page=browser.new_page(viewport={'width':1440,'height':1000})
    calls=[]
    def fail(route):
        calls.append(route.request.url)
        route.fulfill(status=429,body='Rate limited')
    page.route('**/mpc-process-data.js*',fail)
    page.goto(BASE+'/',wait_until='networkidle')
    target=page.locator('#mpc-process')
    target.scroll_into_view_if_needed()
    retry=target.get_by_role('button',name='Retry',exact=True)
    retry.wait_for()
    assert len(calls)==1,calls
    for _ in range(2):
        page.evaluate('scrollTo(0,0)');page.wait_for_timeout(200)
        target.scroll_into_view_if_needed();page.wait_for_timeout(300)
    assert len(calls)==1,calls
    retry.click();page.wait_for_timeout(500)
    assert len(calls)==2,calls
    page.close()
    print('PASS data 429: scrolling does not retry; explicit Retry makes one request',flush=True)

with sync_playwright() as p:
    browser=p.chromium.launch()
    check_page(browser,'/',5)
    check_page(browser,'/code/index.html',5)
    check_data_retry(browser)
    browser.close()
