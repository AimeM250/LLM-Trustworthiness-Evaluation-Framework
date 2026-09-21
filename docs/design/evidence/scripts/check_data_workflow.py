"""Exercise real data preparation in the browser using an isolated database."""
import atexit
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from zipfile import ZipFile
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
BASE = 'http://127.0.0.1:8768'
temp = tempfile.TemporaryDirectory(prefix='ltef-intake-')
server = subprocess.Popen([sys.executable, '-m', 'ltef.webapp', '--port', '8768', '--database', str(Path(temp.name)/'checks.sqlite3')], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def cleanup():
    if server.poll() is None:
        server.terminate()
        server.wait(timeout=10)
    temp.cleanup()
atexit.register(cleanup)
for _ in range(80):
    if server.poll() is not None:
        raise RuntimeError('Isolated server failed to start')
    try:
        urlopen(BASE+'/api/bootstrap',timeout=1).close()
        break
    except OSError:
        time.sleep(.1)
else:
    raise RuntimeError('Server startup timed out')

with sync_playwright() as pw:
    browser=pw.chromium.launch()
    context=browser.new_context(viewport={'width':1440,'height':1050},reduced_motion='reduce')
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def screenshot(name):
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(ROOT/'runs/web'/('data-'+name+'.png')),full_page=True)
    def signup(email):
        page.goto(BASE+'/#signup')
        for field,value in [('name','Data test user'),('email',email),('password','Temporary-data-check-2026!')]:
            page.locator('[name='+field+']').fill(value)
        page.get_by_role('button',name='Create account',exact=True).click()
        expect(page.get_by_role('heading',name='Your evaluation workspace.')).to_be_visible()
    signup('intake-admin@example.test')
    page.locator('.nav-item[href="#data"]').click()
    expect(page.get_by_role('heading',name='What do you want to understand?')).to_be_visible()
    expect(page.locator('#selected-metric-count')).to_have_text('4')
    screenshot('choose')
    page.locator('#view-requirements').click()
    expect(page.get_by_role('heading',name='Three files. One clear contract.')).to_be_visible()
    expect(page.locator('.requirement-details details')).to_have_count(4)
    page.locator('.requirement-details summary').first.click()
    expect(page.locator('.requirement-details details').first).to_have_attribute('open','')
    with page.expect_download() as pending:
        page.locator('#download-starter').click()
    download=pending.value
    with ZipFile(download.path()) as archive:
        profile=json.loads(archive.read('profile.json'))
        assert len(profile['metrics'])==4 and profile['sector']=='finance'
        files={key:archive.read(key+ext) for key,ext in [('cases','.jsonl'),('observations','.json'),('profile','.json')]}
    screenshot('requirements')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    screenshot('mobile')
    page.locator('.preparation-aside [data-prep-step="3"]').click()
    expect(page.locator('#validate-data')).to_be_disabled()
    def choose(key,content):
        page.locator('#data-file-'+key).set_input_files({'name':key+('.jsonl' if key=='cases' else '.json'),'mimeType':'application/json','buffer':content})
    for key,content in files.items(): choose(key,content)
    before=len(page.request.get(BASE+'/api/bootstrap').json()['runs'])
    page.locator('#validate-data').click()
    expect(page.get_by_role('heading',name='Your files have a valid structure.')).to_be_visible()
    assert len(page.request.get(BASE+'/api/bootstrap').json()['runs'])==before
    expect(page.locator('.readiness-table tbody tr')).to_have_count(4)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    screenshot('check-mobile')
    # Replacing any file revokes readiness; mismatched hashes cannot be run.
    bad=json.loads(files['observations'])
    bad['records'][0]['prompt_sha256']='0'*64
    choose('observations',json.dumps(bad).encode())
    expect(page.locator('#prepared-run-form')).to_have_count(0)
    page.locator('#validate-data').click()
    expect(page.get_by_role('heading',name='Some fields need attention.')).to_be_visible()
    expect(page.locator('.readiness-result.invalid')).to_contain_text('prompt hash')
    choose('observations',files['observations'])
    page.locator('#validate-data').click()
    expect(page.get_by_role('heading',name='Your files have a valid structure.')).to_be_visible()
    page.set_viewport_size({'width':1440,'height':1050})
    screenshot('check')
    page.locator('#prepared-run-form [name=name]').fill('Prepared evidence check')
    page.locator('#prepared-run-form button').click()
    expect(page.get_by_role('heading',name='Prepared evidence check',exact=True)).to_be_visible()
    assert len(page.request.get(BASE+'/api/bootstrap').json()['runs'])==before+1
    # Healthcare without clinical reviews must report missing, not zero errors.
    raw=page.request.get(BASE+'/api/templates?sector=healthcare&metrics=major_clinical_error_rate').body()
    with ZipFile(BytesIO(raw)) as archive:
        clinical={key:archive.read(key+ext) for key,ext in [('cases','.jsonl'),('observations','.json'),('profile','.json')]}
    page.goto(BASE+'/#data')
    expect(page.locator('[data-prep-step="3"]')).to_be_visible()
    page.locator('.preparation-steps [data-prep-step="3"]').click()
    for key,content in clinical.items(): choose(key,content)
    page.locator('#validate-data').click()
    expect(page.locator('.readiness-table tbody tr')).to_have_count(1)
    expect(page.locator('.readiness-table tbody tr')).to_contain_text('0 / 32')
    page.goto(BASE+'/#account')
    page.get_by_role('button',name='Sign out').click()
    expect(page.get_by_role('heading',name='Welcome back.')).to_be_visible()
    signup('intake-viewer@example.test')
    page.goto(BASE+'/#data')
    expect(page.locator('#view-requirements')).to_be_visible()
    page.locator('#view-requirements').click()
    expect(page.locator('#download-starter')).to_have_count(0)
    page.locator('.preparation-steps [data-prep-step="3"]').click()
    expect(page.get_by_role('heading',name='Data checks are a Researcher tool.')).to_be_visible()
    assert not errors, errors
    browser.close()
print('PASS: selection, field guidance, ZIP download, valid/invalid preflight, non-persistence, readiness invalidation, upload/run, missing clinical reviews, role restrictions, desktop/mobile, no JS errors')
