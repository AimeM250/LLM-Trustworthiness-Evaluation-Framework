"""Browser integration checks; uses only a temporary database and test accounts."""
from pathlib import Path
import atexit, json, subprocess, sys, tempfile, time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
BASE = 'http://127.0.0.1:8767'
SHOTS = ROOT / 'runs/web'
SHOTS.mkdir(parents=True, exist_ok=True)
PASSWORD = 'Browser-check-only-2026!'
ADMIN_EMAIL, VIEWER_EMAIL = 'browser-admin@example.test', 'browser-viewer@example.test'
temporary = tempfile.TemporaryDirectory(prefix='ltef-browser-check-')
server = subprocess.Popen([sys.executable, '-m', 'ltef.webapp', '--port', '8767', '--database', str(Path(temporary.name)/'workspace.sqlite3')], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def cleanup():
    if server.poll() is None:
        server.terminate()
        server.wait(timeout=10)
    temporary.cleanup()
atexit.register(cleanup)
for attempt in range(80):
    if server.poll() is not None:
        raise RuntimeError('Isolated server exited; port 8767 may be occupied')
    try:
        urlopen(BASE+'/api/bootstrap', timeout=1).close()
        break
    except OSError:
        time.sleep(.1)
else:
    raise RuntimeError('Isolated test server did not start')

def snapshot(page, name):
    page.evaluate('document.fonts.ready')
    page.screenshot(path=str(SHOTS/('redesign-'+name+'.png')),full_page=True)

def no_overflow(page, name):
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), (name,page.evaluate("Array.from(document.querySelectorAll('*')).filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>[e.tagName,e.className,e.getBoundingClientRect().right]).slice(0,20)"))

def route(page, value, heading=None):
    page.goto(BASE+'#'+value)
    if heading:
        expect(page.get_by_role('heading',name=heading,exact=True)).to_be_visible()
    else:
        expect(page.locator('#page-body')).to_be_visible()

def signup(page, name, email):
    page.goto(BASE+'#signup')
    expect(page.locator('#auth-form')).to_be_visible()
    for key,value in [('name',name),('email',email),('password',PASSWORD)]:
        page.locator('input[name="'+key+'"]').fill(value)
    page.get_by_role('button',name='Create account',exact=True).click()
    expect(page.get_by_role('heading',name='Your evaluation workspace.',exact=True)).to_be_visible()

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width':1440,'height':1050},reduced_motion='reduce')
    page = context.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    public=page.request.get(BASE+'/api/bootstrap').json()
    assert public['user'] is None and public['runs']==[] and public['metric_access']==[]
    assert page.request.get(BASE+'/api/runs/not-a-run').status==401
    assert page.request.get(BASE+'/api/users').status==401
    assert page.request.get(BASE+'/api/bootstrap',headers={'Origin':'https://example.com'}).status==403
    assert page.request.get(BASE+'/../README.md').status==404
    page.goto(BASE)
    expect(page.get_by_role('heading',name='Confidence, backed by evidence.')).to_be_visible()
    snapshot(page,'landing')
    page.set_viewport_size({'width':390,'height':844})
    no_overflow(page,'public landing')
    page.set_viewport_size({'width':1440,'height':1050})
    signup(page,'Browser Administrator',ADMIN_EMAIL)
    boot=page.request.get(BASE+'/api/bootstrap').json()
    assert boot['user']['role']=='admin' and len(boot['metric_access'])==18
    sample_id=boot['runs'][0]['id']
    snapshot(page,'workspace')
    for group,count in [('quality',3),('safety',5),('agents',7),('efficiency',3)]:
        page.locator('#tab-'+group).click()
        expect(page.locator('.metric-list-row')).to_have_count(count)
        expect(page.locator('#tab-'+group)).to_have_attribute('aria-pressed','true')
    trigger=page.locator('[data-metric="latency_ms"]')
    trigger.click()
    expect(page.get_by_role('heading',name='Response latency',exact=True)).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('#dialog')).not_to_be_visible()
    expect(trigger).to_be_focused()

    viewer_context=browser.new_context(viewport={'width':1440,'height':1050},reduced_motion='reduce')
    viewer=viewer_context.new_page()
    viewer.on('pageerror',lambda error:errors.append(str(error)))
    signup(viewer,'Browser Viewer',VIEWER_EMAIL)
    view_boot=viewer.request.get(BASE+'/api/bootstrap').json()
    assert view_boot['user']['role']=='viewer' and len(view_boot['metric_access'])==6
    viewer.locator('#tab-safety').click()
    expect(viewer.get_by_text('A deeper view, with Researcher access.',exact=True)).to_be_visible()
    snapshot(viewer,'viewer')
    r=viewer.request.get(BASE+'/api/runs/'+sample_id).json()['report']
    for system in r['systems'].values():
        assert len(system['metrics'])==6 and 'attack_success_rate' not in system['metrics']
    assert set(r['profile']['metrics']) <= set(view_boot['metric_access'])
    assert all(set(row['metrics']) <= set(view_boot['metric_access']) for row in r['case_results'])
    assert viewer.request.get(BASE+'/api/runs/'+sample_id+'/export').status==403
    assert viewer.request.get(BASE+'/api/runs/'+sample_id+'/comparison?baseline=fixture-baseline&candidate=fixture-candidate').status==403
    assert viewer.request.post(BASE+'/api/runs',data={'mode':'demo','sector':'finance'},headers={'X-LTEF-Token':view_boot['token']}).status==403
    route(viewer,'compare/'+sample_id,'Comparison is a Researcher tool.')
    route(viewer,'results/'+sample_id)
    expect(viewer.locator('#result-tab-metrics')).to_be_visible()
    viewer.locator('#result-tab-metrics').click()
    viewer.locator('#tab-safety').click()
    expect(viewer.get_by_role('heading',name='These results require Researcher access.')).to_be_visible()

    route(page,'account','Your account. Your access.')
    person=page.locator('.person-row').filter(has_text=VIEWER_EMAIL)
    expect(person).to_be_visible()
    person.locator('select[name="role"]').select_option('researcher')
    person.get_by_role('button',name='Save role').click()
    expect(page.locator('#toast')).to_have_text('Role updated.')
    viewer.reload()
    expect(viewer.locator('.header-end .role-pill')).to_have_text('Researcher')
    elevated=viewer.request.get(BASE+'/api/bootstrap').json()
    assert len(elevated['metric_access'])==18 and elevated['permissions']['can_run']
    assert len(viewer.request.get(BASE+'/api/runs/'+sample_id).json()['report']['systems']['fixture-candidate']['metrics'])==18
    viewer.locator('#result-tab-metrics').click()
    viewer.locator('#tab-safety').click()
    expect(viewer.locator('.table-metric')).to_have_count(5)

    route(page,'account','Your account. Your access.')
    page.get_by_role('button',name='Sign out',exact=True).click()
    expect(page.get_by_role('heading',name='Welcome back.',exact=True)).to_be_visible()
    assert page.request.get(BASE+'/api/runs/'+sample_id).status==401
    snapshot(page,'signin')
    page.locator('input[name="email"]').fill(ADMIN_EMAIL)
    page.locator('input[name="password"]').fill('Wrong-password-for-test!')
    page.get_by_role('button',name='Sign in',exact=True).click()
    expect(page.locator('#auth-error')).to_be_visible()
    page.locator('input[name="email"]').focus()
    page.keyboard.press('Tab')
    expect(page.locator('#auth-password')).to_be_focused()
    page.keyboard.press('ControlOrMeta+A')
    page.keyboard.type(PASSWORD)
    page.keyboard.press('Enter')
    expect(page.get_by_role('heading',name='Your evaluation workspace.',exact=True)).to_be_visible()

    page.locator('[data-action="new"]').click()
    page.locator('#run-form input[name="name"]').fill('Browser sample evaluation')
    page.locator('#run-form select[name="sector"]').select_option('healthcare')
    page.locator('#run-submit').click()
    expect(page.locator('#dialog')).not_to_be_visible()
    expect(page.get_by_role('heading',name='Browser sample evaluation',exact=True)).to_be_visible()
    for tab in ['metrics','observations','provenance','summary']:
        page.locator('#result-tab-'+tab).click()
        expect(page.locator('#result-tab-'+tab)).to_have_attribute('aria-pressed','true')
        if tab=='metrics':
            page.locator('#tab-safety').click()
            expect(page.locator('.table-metric')).to_have_count(5)
        if tab=='observations':
            page.locator('[data-case]').first.click()
            expect(page.locator('.observation-details')).to_be_visible()
            page.keyboard.press('Escape')
        if tab=='provenance':
            expect(page.locator('.hash-list code')).to_have_count(4)
    page.locator('[data-action="export"]').click()
    with page.expect_download() as result:
        page.get_by_text('Complete JSON',exact=True).click()
    assert result.value.suggested_filename=='ltef-report.json'
    exported=json.loads(Path(result.value.path()).read_text())
    assert exported['profile']['sector']=='healthcare' and exported['evidence_class']=='synthetic_demo'
    page.keyboard.press('Escape')
    page.get_by_role('link',name='Compare systems',exact=True).click()
    expect(page.get_by_text('+78.6 pp',exact=True).first).to_be_visible()
    page.locator('#candidate-select').select_option('fixture-baseline')
    expect(page.get_by_text('Comparison needs different systems',exact=True)).to_be_visible()
    route(page,'evaluations','Your evaluations.')
    page.locator('[data-action="new"]').click()
    page.get_by_text('My own files',exact=True).click()
    page.locator('#run-form input[name="name"]').fill('Browser uploaded evaluation')
    for key,filename in [('cases','cases.jsonl'),('observations','observations.json'),('profile','profiles/finance.json')]:
        page.locator('#run-form input[name="'+key+'"]').set_input_files(str(ROOT/'examples'/filename))
    page.locator('#run-submit').click()
    expect(page.get_by_role('heading',name='Browser uploaded evaluation',exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_role('heading',name='Browser uploaded evaluation',exact=True)).to_be_visible()

    page.set_viewport_size({'width':390,'height':844})
    for tab in ['summary','metrics','observations','provenance']:
        page.locator('#result-tab-'+tab).click()
        expect(page.locator('#result-tab-'+tab)).to_have_attribute('aria-pressed','true')
        no_overflow(page,'mobile result '+tab)
    for target,heading in [('workspace','Your evaluation workspace.'),('evaluations','Your evaluations.'),('account','Your account. Your access.'),('resources',None)]:
        route(page,target,heading)
        no_overflow(page,'mobile '+target)
        if target=='workspace':
            assert page.locator('.run-name').first.bounding_box()['width'] > 230, 'Mobile evaluation title is squeezed'
            snapshot(page,'mobile')
    route(page,'workspace','Your evaluation workspace.')
    page.locator('[data-action="menu"]').click()
    expect(page.locator('#sidebar')).to_have_class('sidebar open')
    expect(page.locator('[data-action="menu"]')).to_have_attribute('aria-expanded','true')
    page.keyboard.press('Escape')
    expect(page.locator('[data-action="menu"]')).to_be_focused()
    page.locator('[data-action="menu"]').click()
    page.locator('#sidebar .nav-item[href="#evaluations"]').click()
    expect(page.get_by_role('heading',name='Your evaluations.',exact=True)).to_be_visible()
    expect(page.locator('#sidebar')).not_to_have_class('sidebar open')
    route(page,'account','Your account. Your access.')
    page.get_by_role('button',name='Sign out',exact=True).click()
    expect(page.get_by_role('heading',name='Welcome back.',exact=True)).to_be_visible()
    no_overflow(page,'mobile sign in')
    page.get_by_role('link',name='Create an account',exact=True).click()
    expect(page.get_by_role('heading',name='Create your account.',exact=True)).to_be_visible()
    no_overflow(page,'mobile sign up')
    assert not errors,errors
    browser.close()
print('PASS: public/auth, roles and protected API, role change, sample/upload, exports, comparisons, metric/case details, keyboard, desktop/mobile; no JavaScript errors')
print('Screenshots: '+str(SHOTS/'redesign-{landing,signin,workspace,viewer,mobile}.png'))
