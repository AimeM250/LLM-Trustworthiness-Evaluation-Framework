from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
out=root/'docs/design'
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':960})
    page.goto((out/'technical-design.html').as_uri())
    assert page.locator('figure svg').count()==5 and page.locator('.requirement').count()==28
    page.pdf(path=str(out/'technical-design.pdf'),print_background=True,prefer_css_page_size=True,display_header_footer=True,header_template='<span></span>',footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#657089">LTEF · Technical design and evidence matrix &nbsp; | &nbsp; <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
    page.screenshot(path=str(root/'runs/web/design-preview.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.set_viewport_size({'width':1440,'height':960})
    previews=[]
    for name in ['01-architecture','02-data-readiness','03-run-sequence','04-data-model','05-evidence-traceability']:
        page.goto((out/f'{name}.svg').as_uri())
        page.screenshot(path=str(root/'runs/web'/f'{name}.png'))
        previews.append('<section>'+ (out/f'{name}.svg').read_text()+'</section>')
    page.goto('about:blank')
    page.set_content('<html><head><style>@page{size:A3 landscape;margin:12mm}body{margin:0}section{break-after:page}section:last-child{break-after:auto}svg{display:block;width:100%;height:auto;max-height:270mm}</style></head><body>'+''.join(previews)+'</body></html>')
    page.pdf(path=str(out/'diagrams.pdf'),print_background=True,prefer_css_page_size=True)
    browser.close()
print('Rendered final technical design PDF and five-page diagram PDF; checked mobile design layout')
