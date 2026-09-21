'use strict';

// Input files stay in memory and are discarded when the account changes.
function freshPreparation() {
  return {step:1, sector:'finance', selected:['reference_accuracy','latency_ms','total_tokens','cost_usd'], catalog:null, loading:false, error:'', files:{}, revision:0, checked:null, payload:null, busy:false};
}
let preparation = freshPreparation();
function resetPreparation(){preparation=freshPreparation();}
async function loadRequirements(){
  if(preparation.catalog||preparation.loading)return;
  const target=preparation;target.loading=true;
  try{const data=await api('/api/data-requirements');if(target!==preparation)return;target.catalog=data;target.error='';}
  catch(error){if(target===preparation)target.error=error.message;}
  finally{if(target===preparation){target.loading=false;if(state.view==='data')render();}}
}
function dataPage(){
  const p=preparation;
  return `${pageHeading('Good evidence starts here.','Choose what to measure. See what to provide. Check it before you run.')}
    <nav class="preparation-steps" aria-label="Data preparation steps">${[['Choose metrics','Define your scope'],['Prepare data','Collect the evidence'],['Check & run','Review what is measurable']].map(([title,sub],i)=>`<button data-prep-step="${i+1}" ${p.busy?'disabled':''} aria-current="${p.step===i+1?'step':'false'}"><span class="step-number">${i+1}</span><span><strong>${title}</strong><small>${sub}</small></span>${icon('chevron')}</button>`).join('')}</nav>
    ${!p.catalog?`<div class="preparation-loading">${p.error?`<p role="alert">${esc(p.error)}</p><button class="button secondary" id="retry-requirements">Try again</button>`:busyPage()}</div>`:p.step===1?chooseDataMetrics():p.step===2?prepareData():checkData()}`;
}
function chooseDataMetrics(){
  const p=preparation;
  return `<div class="preparation-layout"><section class="preparation-main"><div class="section-title"><div><span class="eyebrow">01 / SET THE SCOPE</span><h2>What do you want to understand?</h2><p>Start small. Add measurements as your evidence grows.</p></div></div><label class="field preparation-sector">Evaluation sector<select id="preparation-sector">${Object.entries(sectors).map(([id,n])=>`<option value="${id}" ${p.sector===id?'selected':''}>${n}</option>`).join('')}</select></label>
    <div class="metric-choice-groups">${groups.map((g,i)=>`<details ${i===0?'open':''}><summary>${icon(g.icon)}<span><strong>${g.name}</strong><small>${g.description}</small></span>${icon('down')}</summary><div class="metric-choices">${g.ids.map(id=>{const eligible=id!=='major_clinical_error_rate'||p.sector==='healthcare';return `<label class="metric-choice ${!allowed(id)||!eligible?'unavailable':''}"><input type="checkbox" data-select-metric="${id}" ${p.selected.includes(id)?'checked':''} ${!allowed(id)||!eligible?'disabled':''}><span><strong>${copy[id][0]}</strong><small>${!allowed(id)?'Researcher access required':!eligible?'Available for healthcare cases':copy[id][1]}</small></span></label>`;}).join('')}</div></details>`).join('')}</div></section>
    <aside class="preparation-aside"><span class="eyebrow">YOUR EVALUATION</span><h2><span id="selected-metric-count">${p.selected.filter(allowed).length}</span> metrics</h2><p>Requirements adapt to your selection. You can read them before collecting any data.</p><div class="provision-summary"><span>${icon('file')}A case dataset</span><span>${icon('layers')}Recorded observations</span><span>${icon('shield')}An evaluation profile</span></div><button class="button primary" id="view-requirements" ${p.selected.filter(allowed).length?'':'disabled'}>See requirements ${icon('arrow')}</button><p class="field-hint">${state.permissions.can_run?'Templates contain synthetic examples. Replace them with evidence from your own evaluation.':'You can explore the requirements. A Researcher or Administrator can upload data and run evaluations.'}</p></aside></div>`;
}
function prepareData(){
  const p=preparation, selected=p.catalog.metrics.filter(m=>p.selected.includes(m.id)&&allowed(m.id));
  return `<div class="preparation-layout"><section class="preparation-main"><div class="section-title"><div><span class="eyebrow">02 / COLLECT THE EVIDENCE</span><h2>Three files. One clear contract.</h2><p>${sectors[p.sector]} · ${selected.length} selected metrics</p></div></div><div class="provision-files">${[
    ['01','cases.jsonl','What you asked','One case per line: an ID, sector, source, synthetic flag, and conversation messages. Add references, scenario flags, or agent policies as your selected metrics require.','Dataset owner'],
    ['02','observations.json','What the system did','System and model versions, generation settings, expected trials, and recorded responses or errors. Include a prompt fingerprint for each record and any required measurements or annotations.','Engineer + reviewer'],
    ['03','profile.json','What to measure','Sector, metric IDs, minimum case count, and group dimensions. The starter profile uses your selection. Acceptance thresholds remain uncalibrated.','Evaluation lead']
  ].map(([n,file,title,desc,owner])=>`<article><span class="file-number">${n}</span><div><code>${file}</code><h3>${title}</h3><p>${desc}</p><small>Provided by: ${owner}</small></div></article>`).join('')}</div>
    <div class="section-title requirements-heading"><div><h2>What each metric needs</h2><p>Expand a metric for its exact fields and collection guidance.</p></div></div><div class="requirement-details">${selected.map(m=>`<details><summary><strong>${copy[m.id][0]}</strong>${icon('plus')}</summary><div><p>${esc(m.guidance)}</p><p class="requirement-scope"><strong>Applies when:</strong> ${esc(m.applicability)}</p><ul>${m.required_fields.map(f=>`<li><code>${esc(f)}</code></li>`).join('')}</ul></div></details>`).join('')||'<p>Choose at least one available metric to see its requirements.</p>'}</div>
    <details class="common-contract"><summary>Common requirements for every evaluation ${icon('down')}</summary>${p.catalog.common.map(item=>`<section><h3>${esc(item.title)}</h3><p>${esc(item.guidance)}</p><ul>${item.fields.map(f=>`<li><code>${esc(f)}</code></li>`).join('')}</ul></section>`).join('')}</details></section>
    <aside class="preparation-aside"><span class="eyebrow">A PRACTICAL START</span><h2>Use the starter pack.</h2><p>Download matching files for your sector and metric selection, with instructions for replacing the synthetic examples.</p>${state.permissions.can_run?`<a class="button primary ${selected.length?'':'disabled'}" id="download-starter" href="/api/templates?sector=${p.sector}&metrics=${encodeURIComponent(selected.map(m=>m.id).join(','))}" download>${icon('download')}Download starter pack</a><button class="button secondary" data-prep-step="3">I have my files ${icon('arrow')}</button>`:`<a class="button secondary" href="#account">${icon('lock')}View your access</a>`}<div class="provision-note"><h3>Who supplies the judgments?</h3><p>Claims, unsafe outcomes, refusals, escalation, clinical errors, task success, and error propagation require external annotations. Record the method, evaluator, and rubric version.</p><p>LTEF computes scores from that evidence; it does not independently verify those judgments.</p></div><p class="field-hint">Prompt fingerprints must match the exact messages. The starter README explains how to regenerate them after editing cases.</p></aside></div>`;
}
function checkData(){
  if(!state.permissions.can_run)return lockedState('Data checks are a Researcher tool.','You can explore metric requirements with Viewer access. Your administrator can grant permission to upload and evaluate.');
  const p=preparation;
  return `<div class="preparation-check"><div class="section-title"><div><span class="eyebrow">03 / REVIEW READINESS</span><h2>See what your data can measure.</h2><p>Upload your files to check their structure and measurement coverage. The profile file controls the actual sector and metric selection.</p></div></div><div class="preflight-files">${[['cases','Case dataset','cases.jsonl','.jsonl,.ndjson,.txt'],['observations','Observations','observations.json','.json'],['profile','Evaluation profile','profile.json','.json']].map(([key,title,filename,accept])=>`<label class="preflight-file"><span class="preflight-file-icon">${icon(p.files[key]?'check':'file')}</span><strong>${title}</strong><small>${filename}</small><input type="file" id="data-file-${key}" data-data-file="${key}" accept="${accept}" ${p.busy?'disabled':''}><span class="chosen-file">${p.files[key]?esc(p.files[key].name):'No file selected'}</span></label>`).join('')}</div><div class="preflight-controls"><p>Up to 2,000 cases, 10,000 case/system/trial combinations, and 11 MB combined. Only the evaluation report is stored when you run.</p><button class="button primary" id="validate-data" ${p.busy||Object.keys(p.files).length<3?'disabled':''}>${p.busy?'Working…':'Check data'} ${icon('check')}</button></div><div id="preflight-result" aria-live="polite">${p.error?`<div class="inline-error" role="alert">${esc(p.error)}</div>`:''}${p.checked?readinessResult():`<div class="preflight-explanation"><h3>A check before you commit.</h3><p>This step does not save a report or call a model provider. It identifies invalid fields, missing measurements, and metrics that do not apply to your cases.</p></div>`}</div></div>`;
}
function readinessResult(){
  const r=preparation.checked;
  if(!r.valid)return `<section class="readiness-result invalid"><h2>Some fields need attention.</h2><p>Correct the items below, select the updated files, then check again.</p><ul>${(r.errors||[]).map(e=>`<li>${esc(e)}</li>`).join('')}</ul></section>`;
  return `<section class="readiness-result"><div class="readiness-heading"><span class="readiness-icon">${icon('check')}</span><div><h2>Your files have a valid structure.</h2><p>${r.case_count} cases · ${r.system_count} systems · ${r.trials} trials per system. Review coverage before running.</p></div>${pill(r.evidence_class==='synthetic_demo'?'Synthetic examples':'Unverified imported evidence','sample')}</div>${r.warnings?.length?`<details class="readiness-warnings" open><summary>${r.warnings.length} points to review</summary><ul>${r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></details>`:''}<div class="table-scroll"><table class="readiness-table"><thead><tr><th>Metric</th><th>Scored / eligible</th><th>Missing</th><th>Errors</th><th>Not applicable</th><th>Coverage</th></tr></thead><tbody>${r.metrics.map(m=>`<tr><td>${esc(copy[m.id]?.[0]||m.title)}</td><td>${m.scored} / ${m.eligible}</td><td>${m.missing}</td><td>${m.error??0}</td><td>${m.not_applicable}</td><td>${m.coverage==null?'—':pct(m.coverage)}</td></tr>`).join('')}</tbody></table></div><p class="field-hint">Counts combine all systems and trials. Missing evidence is not a pass. A valid file structure does not establish accuracy, safety, or sufficient sample size.</p><form id="prepared-run-form" class="prepared-run-form"><label class="field">Evaluation name<input name="name" required maxlength="120" value="My evaluation" ${preparation.busy?'disabled':''}></label><button type="submit" class="button primary" ${preparation.busy?'disabled':''}>${preparation.busy?'Evaluating…':'Run evaluation'} ${icon('arrow')}</button></form></section>`;
}
function bindData(){
  if(state.view!=='data')return;
  document.querySelectorAll('[data-prep-step]').forEach(b=>b.onclick=()=>{if(preparation.busy)return;preparation.step=Number(b.dataset.prepStep);render();$('#page-body').scrollIntoView({block:'start'});});
  $('#retry-requirements')?.addEventListener('click',loadRequirements);
  $('#preparation-sector')?.addEventListener('change',e=>{preparation.sector=e.target.value;if(e.target.value!=='healthcare')preparation.selected=preparation.selected.filter(id=>id!=='major_clinical_error_rate');render();});
  document.querySelectorAll('[data-select-metric]').forEach(input=>input.onchange=()=>{const id=input.dataset.selectMetric;if(input.checked)preparation.selected.push(id);else preparation.selected=preparation.selected.filter(x=>x!==id);const n=preparation.selected.filter(allowed).length;$('#selected-metric-count').textContent=n;$('#view-requirements').disabled=!n;});
  $('#view-requirements')?.addEventListener('click',()=>{preparation.step=2;render();$('#page-body').scrollIntoView({block:'start'});});
  document.querySelectorAll('[data-data-file]').forEach(input=>input.onchange=()=>{if(preparation.busy)return;const file=input.files[0],key=input.dataset.dataFile;if(file)preparation.files[key]=file;else delete preparation.files[key];preparation.revision++;preparation.checked=null;preparation.payload=null;preparation.error='';render();});
  $('#validate-data')?.addEventListener('click',validatePreparedData);
  if($('#prepared-run-form'))$('#prepared-run-form').onsubmit=runPreparedData;
}
async function validatePreparedData(){
  const p=preparation,epoch=state.authEpoch,revision=p.revision;
  if(p.busy||!state.permissions.can_run)return;
  p.busy=true;p.error='';p.checked=null;p.payload=null;render();
  try{
    const payload={mode:'upload'},files=['cases','observations','profile'].map(k=>p.files[k]);
    if(files.some(f=>!f))throw Error('Choose all three input files.');
    if(files.reduce((sum,f)=>sum+f.size,0)>11*1024*1024)throw Error('Combined files must be below 11 MB.');
    for(const key of ['cases','observations','profile'])payload[key]=await p.files[key].text();
    if(p!==preparation||epoch!==state.authEpoch)return;
    const result=await api('/api/validate',{method:'POST',body:JSON.stringify(payload)});
    if(p!==preparation||revision!==p.revision||epoch!==state.authEpoch)return;
    p.checked=result;if(result.valid)p.payload=payload;
  }catch(error){if(p===preparation)p.error=error.message;}
  finally{if(p===preparation){p.busy=false;if(state.view==='data')render();}}
}
async function runPreparedData(event){
  event.preventDefault();const p=preparation;
  if(p.busy||!p.checked?.valid||!p.payload||!state.permissions.can_run)return;
  const name=event.target.elements.name.value;p.busy=true;p.error='';render();
  try{const result=await api('/api/runs',{method:'POST',body:JSON.stringify({...p.payload,name})});if(p!==preparation)return;await refreshSession();if(p!==preparation)return;state.resultsTab='summary';navigate('results/'+result.id);toast('Evaluation complete. Your report is saved.');}
  catch(error){if(p===preparation)p.error=error.message;}
  finally{if(p===preparation){p.busy=false;if(state.view==='data')render();}}
}
function designResources(){return `<section class="design-resources"><div><span class="eyebrow">FROM REQUIREMENT TO EVIDENCE</span><h2>The technical design.</h2><p>Business requirements, architecture, data contracts, and implementation evidence in one reviewable package.</p></div><div><a href="/design/technical-design.html" target="_blank" rel="noopener" class="button secondary">Read the design ${icon('arrowUp')}</a><a href="/design/design-package.zip" download class="button secondary">${icon('download')}Download design package</a><p><a href="/design/evidence-matrix.csv" download>Evidence matrix</a><span> · </span><a href="/design/LTEF-technical-design.drawio" download>Editable draw.io diagrams</a></p></div></section>`;}
