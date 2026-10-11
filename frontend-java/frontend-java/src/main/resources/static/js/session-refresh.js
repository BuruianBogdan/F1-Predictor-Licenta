/* Explicit, shared session refresh. Source refusals remain visible; playback is preserved. */
(()=>{'use strict';const dialog=document.getElementById('session-refresh-dialog');if(!dialog)return;
 const $=id=>document.getElementById(id),buttons=[...document.querySelectorAll('[data-refresh-sessions]')],base='/race-control/api/sessions/refresh';let timer=null,pending=false,lastCompleted=null,refreshChanged=false;
 const ro=()=>localStorage.getItem('f1-lang')==='ro',say=(en,romanian)=>ro()?romanian:en;
 const text=(tag,value)=>{const e=document.createElement(tag);e.textContent=value??'';return e;};
 const date=value=>value?new Date(value).toLocaleString(ro()?'ro-RO':'en-GB',{dateStyle:'short',timeStyle:'short'}):'';
 async function api(method='GET'){const r=await fetch(base,{method,cache:'no-store',headers:method==='POST'?{'Content-Type':'application/json'}:{},body:method==='POST'?'{}':undefined});const d=await r.json();if(!r.ok)throw Error(d.error?.message||say('The update service is unavailable.','Serviciul de actualizare nu este disponibil.'));return d;}
 function draw(state){const busy=['QUEUED','RUNNING'].includes(state.status),p=state.progress||{},result=state.result||p;
  buttons.forEach(b=>b.setAttribute('aria-busy',String(busy)));$('session-refresh-again').disabled=busy;$('session-refresh-progress').hidden=!busy;
  const messages={QUEUED:say('Waiting for the current operation…','Așteaptă operația curentă…'),CATALOG:say('Checking the latest session schedule…','Verific programul actualizat al sesiunilor…'),RESULTS:say('Updating published results and predictions…','Actualizez rezultatele publicate și predicțiile…'),ARCHIVE:p.message};
  $('session-refresh-status').textContent=state.status==='FAILED'?state.error:busy?(messages[p.phase]||messages.QUEUED):result.status==='PARTIAL'?say('Check complete. Some data is not available from the source yet.','Verificare terminată. Unele date nu sunt încă disponibile la sursă.'):state.status==='SUCCESS'?say('All available weekend sessions have been updated.','Toate sesiunile disponibile ale weekendului au fost actualizate.'):say('Ready to check the weekend.','Pregătit pentru verificarea weekendului.');
  $('session-refresh-race').textContent=result.race_name||p.race_name||'';const list=$('session-refresh-list');list.replaceChildren();
  const labels={DOWNLOADED:say('Replay ready','Reluare disponibilă'),DOWNLOADING:say('Downloading replay','Se descarcă reluarea'),REPLAY:say('Waiting for public archive download','În așteptarea descărcării arhivei'),UPCOMING:say('Scheduled','Programată'),LIVE_WINDOW:say('Live window / live access not confirmed','Interval live / accesul live nu este confirmat')};
  for(const row of result.sessions||p.sessions||[]){const li=text('li',''),copy=text('div','');copy.append(text('strong',row.name),text('small',(labels[row.status]||row.status)+' · '+date(row.starts_at)));li.append(copy);
   if(row.replay_url||row.viewer_url){const link=text('a',row.downloaded?say('Open replay ↗','Deschide reluarea ↗'):say('Race Control ↗','Race Control ↗'));link.href=row.replay_url||row.viewer_url;li.append(link);}list.append(li);}
  const warnings=$('session-refresh-warnings');warnings.replaceChildren();for(const warning of result.warnings||[]){const label=warning.includes('not public in the archive yet')?say('Public OpenF1 access is temporarily restricted during the live session. Downloaded replays remain available.','Accesul public OpenF1 este temporar restricționat în timpul sesiunii live. Reluările descărcate rămân disponibile.'):warning;warnings.append(text('p',label));}
  $('session-refresh-time').textContent=result.checked_at?say('Checked: ','Verificat: ')+date(result.checked_at):'';
  if(!busy&&state.status==='SUCCESS'&&state.id!==lastCompleted){lastCompleted=state.id;refreshChanged=true;window.dispatchEvent(new CustomEvent('sessions-refreshed',{detail:result}));}
  clearTimeout(timer);if(busy)timer=setTimeout(poll,1500);
 }
 async function poll(){try{draw(await api());}catch(e){$('session-refresh-status').textContent=e.message;timer=setTimeout(poll,5000);}}
 async function refresh(){if(!dialog.open)dialog.showModal();document.querySelector('.tools-menu')?.removeAttribute('open');if(pending)return;pending=true;$('session-refresh-status').textContent=say('Starting the session check…','Pornesc verificarea sesiunilor…');try{draw(await api('POST'));}catch(e){$('session-refresh-status').textContent=e.message;$('session-refresh-progress').hidden=true;}finally{pending=false;}}
 buttons.forEach(b=>b.addEventListener('click',refresh));$('session-refresh-again').onclick=refresh;$('session-refresh-close').onclick=()=>dialog.close();dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
 dialog.addEventListener('close',()=>{if(refreshChanged&&!location.pathname.startsWith('/race-control'))location.reload();});
 window.addEventListener('beforeunload',()=>clearTimeout(timer));api().then(draw).catch(()=>{});
})();
