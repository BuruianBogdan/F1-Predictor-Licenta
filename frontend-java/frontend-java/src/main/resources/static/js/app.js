// F1 Predictor — theme + i18n + UX helpers
(function () {
  const THEME_KEY = "f1-theme";
  const LANG_KEY = "f1-lang";

  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    const icon = document.querySelector(".theme-icon");
    if (icon) icon.textContent = t === "light" ? "◑" : "◐";
  }
  const savedTheme = localStorage.getItem(THEME_KEY) || "dark";
  applyTheme(savedTheme);

  document.addEventListener("DOMContentLoaded", function () {
    const toggle = document.getElementById("theme-toggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        const next = (document.documentElement.getAttribute("data-theme") === "light") ? "dark" : "light";
        localStorage.setItem(THEME_KEY, next);
        applyTheme(next);
      });
    }

    const dict = {
      en: {
        "sessions.refresh":"Update all sessions ↻", "sessions.kicker":"WEEKEND DATA", "sessions.title":"Update all sessions.", "sessions.description":"Check the session schedule, refresh published results and download all available weekend replays.", "sessions.note":"A schedule update does not guarantee a live feed. Live data depends on source access; downloaded replays remain available.", "sessions.retry":"Check again ↻",
        "nav.dashboard": "Race center", "nav.predictions": "Predictions",
        "nav.standings": "Standings", "nav.data": "Data", "nav.export": "Export",
        "nav.regulations": "Regulations", "nav.simulator": "Simulator", "nav.championship": "Championship", "nav.drivers": "Drivers", "nav.model": "The model", "nav.tools": "Tools"
      },
      ro: {
        "sessions.refresh":"Actualizează toate sesiunile ↻", "sessions.kicker":"DATELE WEEKENDULUI", "sessions.title":"Actualizează toate sesiunile.", "sessions.description":"Verifică programul, actualizează rezultatele publicate și descarcă toate reluările disponibile din weekend.", "sessions.note":"Actualizarea programului nu garantează un flux live. Datele live depind de accesul oferit de sursă; reluările descărcate rămân disponibile.", "sessions.retry":"Verifică din nou ↻",
        "nav.dashboard": "Centru curse", "nav.predictions": "Predicții",
        "nav.standings": "Clasament", "nav.data": "Date", "nav.export": "Export",
        "nav.regulations": "Regulamente", "nav.simulator": "Simulator", "nav.championship": "Campionat", "nav.drivers": "Piloți", "nav.model": "Modelul", "nav.tools": "Instrumente"
      }
    };
    Object.assign(dict.en, {"footer":"Independent analysis. Prediction ≠ certainty.","race.center":"RACE CENTER","local.data":"Local data","latest.winner":"LATEST RACE WINNER","finish":"FINISH","points":"POINTS","grid":"GRID","race.analysis":"Explore race analysis ↗","evidence":"Evidence before intuition.","signal.note":"Historical data · Temporal validation · Transparent probabilities","next.race":"UP NEXT","run.forecast":"Build a race forecast →","model.favourite":"MODEL FAVOURITE","win.chance":"estimated win probability","model.record":"MODEL TRACK RECORD","winner.accuracy":"Winner accuracy on held-out seasons","current.standings":"Current championship standings","full.standings":"Full standings ↗","last.podium":"Last time out.","last.sync":"Last synchronization","race.forecast":"RACE FORECAST","predict.title":"Who has the edge?","predict.subtitle":"A probability for every driver. The evidence behind every estimate.","season":"Season","race":"Race","prediction.mode":"Prediction mode","run.prediction":"Run prediction ↗","use.market":"Include manual market odds","why":"Why this estimate?","rest.field":"Through the field","forecast.ready":"The grid is ready for analysis.","champ.title":"The season is still a story.","simulate":"Simulate the championship ↗","model.forecast":"Model forecast","data.title":"Good predictions start here.","data.subtitle":"Synchronize facts, check their quality, then train the model.","sync.current":"Sync current season ↗","model.title":"Show the working.","stale":"Data may be stale. Open Data to synchronize the current season.","welcome":"Every race. A new question."});
    Object.assign(dict.ro, {"footer":"Analiză independentă. Predicția nu este certitudine.","race.center":"CENTRU CURSE","local.data":"Date locale","latest.winner":"CÂȘTIGĂTORUL ULTIMEI CURSE","finish":"CLASARE","points":"PUNCTE","grid":"GRILĂ","race.analysis":"Explorează analiza cursei ↗","evidence":"Dovezi înaintea intuiției.","signal.note":"Date istorice · Validare temporală · Probabilități transparente","next.race":"URMĂTOAREA CURSĂ","run.forecast":"Calculează predicția cursei →","model.favourite":"FAVORITUL MODELULUI","win.chance":"probabilitate estimată de victorie","model.record":"REZULTATELE MODELULUI","winner.accuracy":"Acuratețea câștigătorului pe sezoane de test","current.standings":"Clasamentul actual al campionatului","full.standings":"Clasamentul complet ↗","last.podium":"Podiumul ultimei curse.","last.sync":"Ultima sincronizare","race.forecast":"PREDICȚIE DE CURSĂ","predict.title":"Cine are avantajul?","predict.subtitle":"O probabilitate pentru fiecare pilot. Datele din spatele fiecărei estimări.","season":"Sezon","race":"Cursă","prediction.mode":"Modul predicției","run.prediction":"Rulează predicția ↗","use.market":"Include cote introduse manual","why":"De ce această estimare?","rest.field":"Restul grilei","forecast.ready":"Grila este pregătită pentru analiză.","champ.title":"Povestea sezonului continuă.","simulate":"Simulează campionatul ↗","model.forecast":"Prognoza modelului","data.title":"Predicțiile bune încep aici.","data.subtitle":"Sincronizează datele, verifică-le calitatea, apoi antrenează modelul.","sync.current":"Sincronizează sezonul curent ↗","model.title":"Arată calculele.","stale":"Datele pot fi învechite. Deschide Date pentru a sincroniza sezonul curent.","welcome":"Fiecare cursă. O nouă întrebare."});
    Object.assign(dict.en, {"prediction.check":"Check your prediction settings","mode.qualifying":"After qualifying","qualifying.unavailable":"Qualifying results are not available yet. Pre-weekend is selected; run the prediction using the history currently available.","qualifying.hint":"After qualifying is available once qualifying results have been synchronized. You can run Pre-weekend now."});
    Object.assign(dict.ro, {"prediction.check":"Verifică opțiunile predicției","mode.qualifying":"După calificări","qualifying.unavailable":"Rezultatele calificărilor nu sunt încă disponibile. Este selectat modul Pre-weekend; rulează predicția folosind istoricul disponibil.","qualifying.hint":"Modul După calificări devine disponibil după sincronizarea rezultatelor calificărilor. Poți rula acum Pre-weekend."});
    Object.assign(dict.en, {"nav.calendar": "Calendar", "nav.news": "News", "circuit.label": "THE WINNING GROUND", "circuit.unavailable": "Circuit layout unavailable", "calendar.kicker": "THE SEASON, TURN BY TURN", "calendar.title": "Every circuit. A different story.", "calendar.subtitle": "The next lights out. The road to the title.", "calendar.remaining": "TO GO", "calendar.completed": "COMPLETED", "calendar.upcoming": "Next on the calendar", "calendar.order": "IN RACE ORDER", "calendar.raceweek": "RACE WEEKEND", "calendar.none": "No upcoming race in this season’s synchronized calendar.", "calendar.pending": "Awaiting verified results", "calendar.archive": "The season so far", "calendar.recent": "LATEST RESULT FIRST", "calendar.result": "RESULTS ↗", "news.kicker": "FROM THE PADDOCK / FORMULA 1", "news.title": "The stories behind the numbers.", "news.subtitle": "Official reporting. Short AI summaries. Traceable forecast signals.", "news.latest": "Inside the paddock.", "news.all": "All stories ↗", "news.signal": "FORECAST SIGNAL", "news.paddock": "PADDOCK", "news.original": "Read source ↗", "news.pending": "Local summary pending. Read the original article for the complete story.", "news.impact": "How this affects the forecast", "news.stories": "STORIES COLLECTED", "news.refresh": "Refresh news ↻", "news.empty": "The first edition is on its way.", "news.emptytext": "The automatic crawler starts with the application. You can also run a refresh now.", "news.method": "Sources, automation & forecast methodology", "news.methodtext": "Selenium reads public articles on the official Formula 1 website every 30 minutes while this application is running. A local LLM writes short summaries; they may contain mistakes. Always check the linked source.", "news.signaltext": "Only explicitly confirmed, race-specific grid penalties are currently used as experimental forecast signals. General opinions and AI summaries do not change probabilities. Signals are capped and dated to prevent future information from entering historical predictions.", "news.used": "News adjustment included"});
    Object.assign(dict.ro, {"nav.calendar": "Calendar", "nav.news": "Știri", "circuit.label": "CIRCUITUL VICTORIEI", "circuit.unavailable": "Traseu indisponibil", "calendar.kicker": "SEZONUL, VIRAJ CU VIRAJ", "calendar.title": "Fiecare circuit. O altă poveste.", "calendar.subtitle": "Următorul start. Drumul spre titlu.", "calendar.remaining": "RĂMASE", "calendar.completed": "ÎNCHEIATE", "calendar.upcoming": "Următoarele curse", "calendar.order": "ÎN ORDINE CRONOLOGICĂ", "calendar.raceweek": "WEEKEND DE CURSĂ", "calendar.none": "Nu mai sunt curse viitoare în calendarul sincronizat al acestui sezon.", "calendar.pending": "În așteptarea rezultatelor confirmate", "calendar.archive": "Sezonul de până acum", "calendar.recent": "CELE MAI RECENTE PRIMELE", "calendar.result": "REZULTATE ↗", "news.kicker": "DIN PADOC / FORMULA 1", "news.title": "Poveștile din spatele cifrelor.", "news.subtitle": "Știri oficiale. Rezumate AI scurte. Semnale cu surse verificabile.", "news.latest": "Din interiorul padocului.", "news.all": "Toate știrile ↗", "news.signal": "SEMNAL PENTRU PREDICȚII", "news.paddock": "PADOC", "news.original": "Citește sursa ↗", "news.pending": "Rezumat în curs de generare. Citește articolul original pentru detalii.", "news.impact": "Cum influențează predicția", "news.stories": "ȘTIRI COLECTATE", "news.refresh": "Actualizează știrile ↻", "news.empty": "Prima ediție este în pregătire.", "news.emptytext": "Colectarea automată pornește odată cu aplicația. Poți rula și o actualizare manuală.", "news.method": "Surse, automatizare și metodologia predicțiilor", "news.methodtext": "Selenium citește articole publice de pe site-ul oficial Formula 1 la fiecare 30 de minute, cât timp aplicația rulează. Un LLM local scrie rezumate scurte; acestea pot conține erori. Verifică sursa indicată.", "news.signaltext": "În prezent, doar penalizările confirmate pe grilă, asociate unei curse, sunt folosite ca semnale experimentale. Opiniile și rezumatele AI nu modifică probabilitățile. Impactul este limitat, iar data colectării împiedică folosirea informațiilor viitoare în predicții istorice.", "news.used": "Ajustare din știri inclusă"});
    Object.assign(dict.en, {"live.kicker": "LIVE WEEKEND", "live.title": "New session. New evidence.", "live.subtitle": "Collect the latest published results and recalculate the Grand Prix, sprint and championship.", "live.refresh": "Update weekend ↻", "live.last": "Last successful check", "live.partial": "Some updates are unavailable. Previously collected results are retained.", "live.source": "Official results ↗", "live.classification": "Session classification", "live.published": "Updates use published classifications after each session. Practice is weighted lightly because tyres and fuel loads can differ.", "live.updating": "Updating weekend data and predictions…", "live.target": "Event", "live.mode": "Latest weekend data", "live.estimate": "Weekend estimate", "live.estimate.text": "This estimate combines the historical model with available session results. Sprint qualifying contributes to sprint grid expectations; Grand Prix qualifying and its grid remain separate.", "live.method": "Method and assumptions", "live.weekendtab": "WEEKEND", "live.expected": "Expected points", "live.evidence": "Session evidence"});
    Object.assign(dict.ro, {"live.kicker": "WEEKEND ACTUALIZAT", "live.title": "O nouă sesiune. Date noi.", "live.subtitle": "Colectează ultimele rezultate publicate și recalculează Grand Prix-ul, sprintul și campionatul.", "live.refresh": "Actualizează weekendul ↻", "live.last": "Ultima verificare reușită", "live.partial": "Unele actualizări nu sunt disponibile. Rezultatele deja colectate sunt păstrate.", "live.source": "Rezultate oficiale ↗", "live.classification": "Clasamentul sesiunii", "live.published": "Actualizarea folosește clasamentele publicate după sesiuni. Practice-ul are o pondere moderată deoarece pneurile și cantitatea de combustibil pot diferi.", "live.updating": "Se actualizează datele weekendului și predicțiile…", "live.target": "Eveniment", "live.mode": "Datele actuale ale weekendului", "live.estimate": "Estimare pentru weekend", "live.estimate.text": "Estimarea combină modelul istoric cu rezultatele sesiunilor disponibile. Calificările sprintului influențează estimarea pentru sprint; calificările și grila Grand Prix-ului sunt tratate separat.", "live.method": "Metodă și ipoteze", "live.weekendtab": "WEEKEND", "live.expected": "Puncte estimate", "live.evidence": "Datele sesiunilor"});
    function applyLang(lang) {
      const map = dict[lang] || dict.en;
      document.querySelectorAll("[data-i18n]").forEach(function (el) {
        const k = el.getAttribute("data-i18n");
        if (map[k]) el.textContent = map[k];
      });
      document.documentElement.setAttribute("lang", lang);
      document.querySelectorAll('time[data-weekend-time][datetime]').forEach(function(el){
        const date=new Date(el.dateTime);
        if(!Number.isNaN(date.getTime())){
          el.textContent=new Intl.DateTimeFormat(lang==='ro'?'ro-RO':'en-GB',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}).format(date);
          el.title='UTC '+date.toISOString();
        }
      });
    }
    const langSelect = document.getElementById("lang-select");
    const savedLang = localStorage.getItem(LANG_KEY) || "en";
    if (langSelect) {
      langSelect.value = savedLang;
      langSelect.addEventListener("change", function () {
        localStorage.setItem(LANG_KEY, langSelect.value);
        applyLang(langSelect.value);
      });
    }
    applyLang(savedLang);

    const raceSelect = document.getElementById('raceId');
    const modeSelect = document.getElementById('mode');
    const qualifyingNote = document.getElementById('qualifying-note');
    if (raceSelect && modeSelect && qualifyingNote) {
      const updateModes = function () {
        const ready = raceSelect.selectedOptions[0]?.dataset.qualifyingAvailable === 'true';
        const option = modeSelect.querySelector('option[value="POST_QUALIFYING"]');
        option.disabled = !ready;
        const targetSelect=document.getElementById('target');
        const sprint= raceSelect.selectedOptions[0]?.dataset.sprintAvailable === 'true';
        if(targetSelect){
          const sprintOption=targetSelect.querySelector('option[value=SPRINT]');
          sprintOption.disabled=!sprint;
          if(!sprint && targetSelect.value==='SPRINT')targetSelect.value='RACE';
          option.disabled=!ready || targetSelect.value==='SPRINT';
          const input=document.getElementById('refresh-target');if(input)input.value=targetSelect.value;
        }
        const refreshRace=document.getElementById('refresh-race-id');if(refreshRace)refreshRace.value=raceSelect.value;
        qualifyingNote.hidden = ready || targetSelect?.value==='SPRINT';
        const refreshButton=document.querySelector('form[action="/predictions/refresh"] button');
        if(refreshButton)refreshButton.disabled = raceSelect.selectedOptions[0]?.dataset.refreshAvailable !== 'true';
        const marketInput=document.getElementById('marketCheck');
        if(marketInput){marketInput.disabled=targetSelect?.value==='SPRINT';if(marketInput.disabled){marketInput.checked=false;marketInput.dispatchEvent(new Event('change'));}}
        if(option.disabled && modeSelect.value==='POST_QUALIFYING')modeSelect.value=targetSelect?.value==='SPRINT'?'LIVE':'PRE_WEEKEND';
        if (!ready && modeSelect.value === 'POST_QUALIFYING') modeSelect.value = 'PRE_WEEKEND';
      };
      raceSelect.addEventListener('change', updateModes);
      document.getElementById('target')?.addEventListener('change',updateModes);
      updateModes();
    }

    document.querySelectorAll('.nav-links a').forEach(function(a) { if (a.pathname === location.pathname || (a.pathname !== '/' && location.pathname.startsWith(a.pathname+'/'))) a.classList.add('active'); });
    document.querySelectorAll('[data-driver-image]').forEach(function(img) { img.addEventListener('error', function() { if (!this.src.endsWith('driver-silhouette.svg')) this.src='/images/driver-silhouette.svg'; }); });
    document.querySelectorAll('[data-prob-view]').forEach(function(button) {
      button.addEventListener('click', function() {
        document.querySelectorAll('[data-prob-view]').forEach(b => b.classList.toggle('active', b === button));
        document.querySelectorAll('.probability-value').forEach(function(el) {
          const raw = el.dataset[button.dataset.probView];
          el.textContent = raw && raw !== 'null' ? (Number(raw) * 100).toFixed(1) + '%' : 'Unavailable';
        });
      });
    });
    const jobPanel = document.querySelector('[data-job-id]');
    if (jobPanel) {
      const poll = async function() {
        try {
          const response = await fetch('/data/jobs/' + encodeURIComponent(jobPanel.dataset.jobId));
          if (!response.ok) throw new Error('Status unavailable');
          const job = await response.json();
          jobPanel.querySelector('.job-status').textContent = job.label + ' · ' + job.status;
          if (job.status === 'SUCCESS' && jobPanel.dataset.jobAutoRefresh === 'true') {
            location.replace(jobPanel.dataset.jobReturn);return;
          }
          if (job.status === 'SUCCESS' || job.status === 'FAILED') {
            jobPanel.querySelector('.job-result').textContent = JSON.stringify(job.result || job.error, null, 2);
            const link=document.createElement('a');link.href=jobPanel.dataset.jobReturn || '/data';link.className='text-link';link.textContent='View updated page →';jobPanel.appendChild(link);
          } else setTimeout(poll, 2000);
        } catch(error) { jobPanel.querySelector('.job-status').textContent = 'Could not read operation status. Check the backend log or refresh Data.'; }
      };
      poll();
    }
    // Spinner on form submit
    document.querySelectorAll("form[data-spinner]").forEach(function (form) {
      form.addEventListener("submit", function () {
        const btn = form.querySelector("button[type=submit], .btn-calculate");
        if (btn && !btn.disabled) {
          btn.disabled = true;
          const label = btn.textContent;
          btn.dataset.originalLabel = label;
          btn.innerHTML = '<span class="spinner"></span> Working...';
        }
      });
    });

    // Market odds toggle
    const marketCheck = document.getElementById("marketCheck");
    const oddsSection = document.getElementById("odds-section");
    if (marketCheck && oddsSection) {
      function syncOddsVisibility() {
        oddsSection.classList.toggle("visible", marketCheck.checked);
      }
      marketCheck.addEventListener("change", syncOddsVisibility);
      syncOddsVisibility();
    }

    // Add odds row dynamically
    const addOddsBtn = document.getElementById("add-odds-row");
    const oddsGrid = document.getElementById("odds-grid");
    if (addOddsBtn && oddsGrid) {
      addOddsBtn.addEventListener("click", function () {
        const row = document.createElement("div");
        row.className = "odds-row";
        const first = oddsGrid.querySelector('.odds-row');
        if (first) {
          Array.from(first.children).forEach(function (child) { const copy = child.cloneNode(true); copy.value = ''; row.appendChild(copy); });
        }
        oddsGrid.appendChild(row);
      });
    }
  });
})();
