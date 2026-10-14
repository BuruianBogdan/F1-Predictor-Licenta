# Raport final — Live Data v2

Implementarea și verificările locale sunt încheiate pentru această etapă. Validarea pe o sesiune live reală rămâne **PENDING_LIVE_SESSION**; probele istorice și fixture-urile nu sunt prezentate drept dovezi live.

## A. Repository

Ramură: `fix/live-feed-completion`. HEAD inițial și final: `710b7e34ed70161f97a1e1adcc37e02d06cbe89e`. Nu am creat commituri și nu am publicat modificările. Ramura inițială era main. Frontendul/documentația existau deja ca modificări locale; le-am păstrat. Checkoutul separat F1-Predictor-Licenta a rămas neatins. Lista completă a fișierelor din working tree este la final; include fișiere care erau deja necomise la început.

## B. Implementare

Existau providerul SignalR, contractul temporal, checkpointurile, FastF1 fallback, proiecțiile și frontendul local. Am completat diagnosticele vizibile, echipa și schimbarea poziției în clasament, anularea/timeoutul cererilor și resetarea imediată la schimbarea sesiunii. Proiecția folosește un singur frame, inclusiv STOPPED_NOW.

Am corectat confirmarea câștigătorului și versiunea rezultatelor publicate, excluderea corecțiilor de după cutoff, baseline-urile istorice fără moment cunoscut, checkpointurile concurente, latența pachetelor duplicate, booleanul false al frânei, canalele malformed și pachetele din sesiuni anterioare.

Am păstrat Race Control, harta, animațiile, replay-ul, strategia, pneurile, știrile, calendarul, predicțiile și **Tools → Update all sessions**. OCR și platforma separată nu au fost readăugate. Nu am introdus React, SSE sau provideri duplicat fără avantaj demonstrat.

## C. Frontend

Diagnosticele arată provider/sesiune/meeting/transport/identitate, UTC observație versus primire, vechime, retry, recuperare, latență măsurată, erori și canale cerute/disponibile/lipsă. Tabelul arată fiecare dintre cele 12 topicuri, valid events, UTC, age, stare și explicație. Proiecțiile piloți/constructori arată echipa, punctele oficiale înainte de sesiune, punctele provizorii, totalul, poziția și schimbarea ei.

Proxy-ul Java reutilizează FlaskApiService. Timeoutul este 20 secunde; schimbarea sesiunii invalidează răspunsurile vechi, pagehide oprește cererile, iar ferestrele separate continuă independent. Dialogul funcționează cu Escape; piloții pot fi selectați din tastatură. Verificări responsive la 320, 390, 768, 1440 și 1920 px: fără overflow al paginii.

## D. Backend și corectitudinea datelor

SignalR transport connected nu înseamnă LIVE: sunt necesare identitate potrivită și TimingData datat, proaspăt. Heartbeatul nu avansează observațiile. Reconectarea are buget/backoff; refuzurile de acces nu sunt ocolite. Pozițiile/telemetria lipsă rămân lipsă. Sunt verificate limitele, timestampurile, driver scope, intervalele numerice, 0/false/null și recuperarea STALE.

Checkpointurile folosesc fișiere temporare unice, replace atomic și limite de mărime/vechime/context. Datele recuperate nu devin LIVE fără observații noi potrivite. Nu persistă transportul sau credențialele.

Finalised + P1 rămâne provizoriu. Numai clasificarea publicată, verificată și mapată unic confirmă câștigătorul. Corecțiile pot schimba winner-ul. O tranziție finală de replay poate prezenta explicit ultimul rezultat istoric verificat, fără a pretinde că era publicat la cursor. Acest rezultat nu este baseline temporal sau feature pentru predicțiile anterioare.

Sincronizarea Jolpica păstrează acum versiuni R/Q/SPRINT în tabela weekend existentă, cu ora reală a observației locale. Schema SQL rămâne neschimbată. Proiecțiile nu scriu clasamentul oficial. Rezultatele vechi fără moment verificabil sunt excluse din baseline-ul de replay; totalurile sunt ascunse cu UNVERIFIED_BASELINE. Pentru DNF se folosesc tururile completate și pragul de clasificare; DSQ/DNS, schimbări de echipă, dead heat și Sprint o singură dată au teste.

Punctajele acceptate sunt pentru 2019–2026. FULL_DISTANCE este o ipoteză explicită. STOPPED_NOW necesită distanță și tururi verzi observate; 2022 cere și condiția nereînceperii. Regulile vechi de întrerupere nu sunt reconstruite din date insuficiente. Bonusul fastest lap este condițional până în 2024 și absent ulterior.

## E. ML

Modelul on-track-strategy-v1 nu a fost antrenat sau ajustat pe acest benchmark. Patru sesiuni istorice, cinci cutoffuri (10/25/50/75/90%), numai evenimente până la cutoff. Distribuțiile complete, metricele și acoperirea sunt în [evaluation/LIVE_BACKTEST_RESULTS.json](evaluation/LIVE_BACKTEST_RESULTS.json). Clasificarea finală este doar eticheta de evaluare.

| Metodă | Cutoffuri | Top-1 | Top-3 | Brier | Log loss | ECE | Sesiuni cu date suficiente |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_leader | 20 | 90.0% | 90.0% | 0.200 | 2.763 | 0.100 | 4/4 |
| observed_pace | 15 | 66.7% | 66.7% | 0.667 | 9.210 | 0.333 | 3/4 |
| strategy_v1 | 13 | 38.5% | 46.2% | 0.752 | 3.739 | 0.253 | 3/4 |

Strategia are 13/20 cutoffuri utilizabile. Nu există predicție pre-race salvată, eligibilă temporal, pentru această comparație; baseline-ul nu este inventat retrospectiv. Eșantionul este mic, cutoffurile sunt corelate, iar arhivele pot include corecții ulterioare cu latență originală necunoscută. Evaluarea este descriptivă și incompletă pentru calibrare/generalizare. Strategia este sub reperul liderului curent în acest eșantion.

## F. Validation

| Verificare | Comanda executată | Rezultat |
|---|---|---|
| Backend | `RUN_SELENIUM=1 backend-python/.venv/bin/python -m pytest backend-python/tests -q` | PASS |
| Java | `mvn -f frontend-java/frontend-java/pom.xml test package` | PASS |
| Renderer | `node --test scripts/tests/race-control-engine.test.js` | PASS |
| Real replay | `backend-python/.venv/bin/python scripts/verify_race_control.py` | PASS |
| Strategy browser | `backend-python/.venv/bin/python scripts/verify_race_control_strategy.py` | PASS |
| Responsive/proxy | `backend-python/.venv/bin/python scripts/verify_timing_integration.py` | PASS |
| Completion scenarios | `backend-python/.venv/bin/python scripts/verify_live_completion_browser.py` | PASS |
| FastF1 | `backend-python/.venv/bin/python scripts/verify_fastf1_archive.py --browser` | PASS |
| Buffers | `backend-python/.venv/bin/python scripts/verify_timing_buffers.py` | PASS |
| Performance | `backend-python/.venv/bin/python scripts/verify_live_performance.py` | PASS |
| Evaluation | `backend-python/.venv/bin/python scripts/backtest_race_strategy.py` | PASS |
| Sources | `backend-python/.venv/bin/python scripts/verify_live_sources.py --race-id 210 --session R --public-probe --seconds 10 --compare-public-hosts` | PASS |

Backend: **185 passed, 0 skipped**, inclusiv fixture-ul Selenium local. Java: **32 tests**, build package PASS. Renderer: **9 tests**. Browser completion: **26 verificări**, incluzând toate cele 20 de scenarii solicitate, timeout real, pagehide, dialog Escape, reduced motion și inventarul cererilor. Aceste scenarii sunt VERIFIED_FIXTURE. Replay-ul și ferestrele independente au separat verificare pe arhiva reală. Nu sunt erori severe de browser în rapoartele finale.

FastF1 real: VERIFIED_HISTORICAL, Abu Dhabi 2024 R, session 9662; 20 piloți, 1035 tururi, 269967 poziții și 292240 telemetrie. Lotul și câștigătorul coincid cu OpenF1; tururile sunt 1035 versus 1037. Primarul indisponibil și transportul browserului au fost injectate numai în testul izolat; datele FastF1 sunt reale. Arhivele aplicației nu au fost suprascrise.

HTTP frame median/p95 și testul cu doi workeri sunt în [LIVE_PERFORMANCE.md](LIVE_PERFORMANCE.md). Global lock și salvarea sincronă a checkpointului rămân costuri măsurate; nu există o garanție de latență pentru upstream.

Comenzile inițiale de unittest din directorul nepotrivit au avut import errors; verificarea corectă este pytest. Primul test Java al proxy-ului a eșuat deoarece query-ul a primit parametrul scoring; testul a fost actualizat la contractul nou, apoi buildul complet a trecut. Harnessul browser a avut probleme de sincronizare/animație și un restart al serverului în timpul rulării; acestea au fost corectate, iar verificările finale trec. Lipsa unui pilot selectat a evidențiat și o dereferențiere UI, corectată în cod. Aceste eșecuri inițiale nu sunt ascunse ca PASS.

Dovezi finale: [LIVE_COMPLETION_VERIFICATION.json](LIVE_COMPLETION_VERIFICATION.json), [LIVE_COMPLETION_BROWSER.json](LIVE_COMPLETION_BROWSER.json), [RACE_CONTROL_VERIFICATION.json](RACE_CONTROL_VERIFICATION.json), [LIVE_BROWSER_VERIFICATION.json](LIVE_BROWSER_VERIFICATION.json), [LIVE_FINAL_SMOKE.json](LIVE_FINAL_SMOKE.json), [FASTF1_ARCHIVE_VERIFICATION.json](FASTF1_ARCHIVE_VERIFICATION.json). Diff whitespace și scanarea textului modificat pentru credențiale: PASS.

## G. External Sources

Cele opt proiecte au fost reverificate prin documentația/codul/licențele publice; revision și hashurile fișierelor sunt în [LIVE_PROVIDER_AUDIT.json](LIVE_PROVIDER_AUDIT.json). FastF1 este fallback istoric real; OpenF1 este arhiva primară; Jolpica/Formula 1 sunt sursele deja existente pentru clasificări publicate. Nu am copiat cod din alte repo-uri.

Mricero, harsh779, julesr0y și f1-dash folosesc același upstream de timing; nu oferă o sursă independentă demonstrată pentru canalele lipsă. F1 API oferă rezultate publicate, fără un avantaj live GPS/CarData demonstrat. Nu am adăugat adaptoare/dependențe fără avantaj verificat. Comparația cu acces, cost, limite și roluri este în [LIVE_PROVIDER_COMPARISON.md](LIVE_PROVIDER_COMPARISON.md).

Arhivele utilizate sunt accesibile public fără cont în aceste verificări. [Documentația OpenF1](https://openf1.org/docs/) distinge arhivele istorice de accesul live autorizat prin abonament. Licența unui client nu garantează accesul la date; refuzurile nu sunt ocolite. F1 TV/OCR nu fac parte din implementare.

## H. Remaining Limitations

Proba publică a observat sesiunea încheiată, identitate VERIFIED, nu o cursă în desfășurare. Statusul final este **PENDING_LIVE_SESSION**. Nu sunt revendicate poziții sau CarData live. Fără Position.z nu există mișcare live măsurată pe hartă; fără CarData.z nu există telemetrie live măsurată. Timing poate funcționa independent de aceste canale.

La următoarea sesiune: pornește aplicațiile, actualizează catalogul prin Tools Update all sessions, alege race_id/session code din catalog, oprește celelalte conexiuni live ale aplicației și rulează `backend-python/.venv/bin/python scripts/verify_live_sources.py --race-id <id> --session <code> --public-probe --seconds 30`. Confirmarea reală cere sesiune potrivită în RUNNING, observații datate și proaspete; coordonatele/telemetria trebuie confirmate separat.

Momentul original al publicării rezultatelor vechi, unele condiții ale curselor întrerupte, uzura individuală reală a roților și avariile măsurate pe componente nu sunt disponibile. Estimările pneurilor și incidentelor rămân etichetate. Calibrarea extinsă a strategiei și observația unei sesiuni live reale sunt lucrările următoare, nu criterii bifate pe baza fixture-urilor.

## Fișiere create/modificate în working tree

Lista include și modificările locale preexistente păstrate. HEAD nu conține încă aceste schimbări.

- `README.md`
- `backend-python/api/race_control_routes.py`
- `backend-python/data_sources/timing_contract.py`
- `backend-python/services/data_sync_service.py`
- `backend-python/services/race_control_checkpoint.py`
- `backend-python/services/race_control_projection_service.py`
- `backend-python/services/race_control_results.py`
- `backend-python/services/race_control_service.py`
- `backend-python/services/race_strategy_service.py`
- `backend-python/tests/test_live_completion.py`
- `backend-python/tests/test_race_strategy.py`
- `backend-python/tests/test_timing_integration.py`
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/FASTF1_ARCHIVE_VERIFICATION.json`
- `docs/KNOWN_LIMITATIONS.md`
- `docs/LIVE_BACKTESTING.md`
- `docs/LIVE_BACKTEST_RESULTS.json`
- `docs/LIVE_BROWSER_VERIFICATION.json`
- `docs/LIVE_BUFFER_VERIFICATION.json`
- `docs/LIVE_COMPLETION_AUDIT.md`
- `docs/LIVE_COMPLETION_BROWSER.json`
- `docs/LIVE_COMPLETION_REPORT.md`
- `docs/LIVE_COMPLETION_VERIFICATION.json`
- `docs/LIVE_CONNECTION_LIFECYCLE.md`
- `docs/LIVE_DATA_ARCHITECTURE.md`
- `docs/LIVE_DATA_SCHEMA.md`
- `docs/LIVE_DIAGNOSTICS.md`
- `docs/LIVE_FEED_AUDIT.md`
- `docs/LIVE_FINAL_SMOKE.json`
- `docs/LIVE_INTEGRATION_REPORT.md`
- `docs/LIVE_INTEGRATION_VERIFICATION.json`
- `docs/LIVE_LIMITATIONS.md`
- `docs/LIVE_PERFORMANCE.md`
- `docs/LIVE_PERFORMANCE_VERIFICATION.json`
- `docs/LIVE_PROVIDER_AUDIT.json`
- `docs/LIVE_PROVIDER_COMPARISON.md`
- `docs/LIVE_SOURCE_VERIFICATION.json`
- `docs/RACE_CONTROL.md`
- `docs/RACE_CONTROL_VERIFICATION.json`
- `docs/RACE_STRATEGY.md`
- `docs/RACE_STRATEGY_VERIFICATION.json`
- `docs/RUNBOOK.md`
- `docs/TESTING.md`
- `docs/THESIS_NOTES.md`
- `docs/VERIFIED_DEPENDENCIES.json`
- `docs/evaluation/LIVE_BACKTEST_RESULTS.json`
- `docs/screenshots/fastf1-replay-verified.png`
- `docs/screenshots/race-control-desktop.png`
- `docs/screenshots/race-control-gp-start.png`
- `docs/screenshots/race-control-gp-winner.png`
- `docs/screenshots/race-control-mobile.png`
- `docs/screenshots/race-control-session-leader.png`
- `docs/screenshots/race-control-smooth-map.png`
- `docs/screenshots/race-control-standalone.png`
- `docs/screenshots/race-control-start.png`
- `docs/screenshots/race-control-strategy-desktop.png`
- `docs/screenshots/race-control-strategy-mobile.png`
- `docs/screenshots/race-control-tyres-incident.png`
- `docs/screenshots/timing-diagnostics-desktop.png`
- `docs/screenshots/timing-diagnostics-mobile.png`
- `docs/screenshots/timing-projection-desktop.png`
- `frontend-java/frontend-java/src/main/java/com/f1predictor/frontendjava/controller/RaceControlController.java`
- `frontend-java/frontend-java/src/main/resources/static/css/race-control.css`
- `frontend-java/frontend-java/src/main/resources/static/js/race-control.js`
- `frontend-java/frontend-java/src/main/resources/templates/race-control.html`
- `frontend-java/frontend-java/src/test/java/com/f1predictor/frontendjava/FrontendRenderingTests.java`
- `scripts/backtest_race_strategy.py`
- `scripts/verify_fastf1_archive.py`
- `scripts/verify_live_completion_browser.py`
- `scripts/verify_live_performance.py`
- `scripts/verify_live_sources.py`
- `scripts/verify_race_control.py`
- `scripts/verify_race_control_strategy.py`
- `scripts/verify_timing_buffers.py`
- `scripts/verify_timing_integration.py`
