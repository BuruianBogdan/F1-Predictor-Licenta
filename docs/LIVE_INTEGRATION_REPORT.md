> Version 1 historical audit. For the current working tree, winner-confirmation contract and final test results, use [Live Data v2 completion report](LIVE_COMPLETION_REPORT.md).

# Raport de integrare Race Control

Ramură: `codex/live-feed-integration`. Implementarea extinde modulul existent. Testarea unei sesiuni live active rămâne în așteptare; nu este prezentată ca succes o verificare făcută după finalul cursei.

1. **Ce exista deja?** SignalR public fără cont, verificare de cheie, timing tower, reluări OpenF1, harta SVG cu poziții măsurate, sectoare/piloți favoriți, popout, vreme, pneuri/accidente și strategia experimentală v1.
2. **Ce s-a modificat?** Identitatea completă a sesiunii, prospețimea datelor, reîncercări limitate, timeout de negociere, validarea pachetelor, merge cu timestamp-uri, eliminări/indexare corectă, provenance, buffere separate și limitate, checkpoint-uri, fallback FastF1 istoric, RPM, diagnostice, proiecții și evaluare cronologică.
3. **Ce s-a păstrat?** Interfața Race Control, animația/harta/etichetele/landmark-urile, reluarea, ferestrele separate, formula strategiei, predicțiile anterioare, sincronizarea și Tools → Update all sessions. OCR și platforma separată nu au revenit. Schema DB rămâne 3.
4. **Ce proiecte au fost studiate?** Cele opt proiecte/linkuri cerute: mricero, harsh779, julesr0y, FastF1, OpenF1, Jolpica, slowlydev/f1-dash și F1 API. Reviziile, licențele și endpoint-urile verificate sunt în [comparație](LIVE_PROVIDER_COMPARISON.md) și [auditul surselor](LIVE_PROVIDER_AUDIT.json).
5. **Ce cod/idei s-au reutilizat?** Bibliotecile existente și concepte standard de SignalR, state sparse, recuperare și diagnostice. Codul nou este scris în proiect; nu s-au copiat fișiere externe sau cod AGPL. Referințele MIT/Apache/CC și excepțiile pentru date/asset-uri sunt documentate separat; licența codului nu acordă acces la date protejate.
6. **Ce provideri sunt implementați?** PublicTimingFeed îmbunătățit, OpenF1 istoric existent, convertor/fallback FastF1 istoric și Jolpica pentru clasificări publicate/baseline. Nu există un adaptor live extern declarat fictiv validat.
7. **Care este principalul?** `existing_public_timing` pentru live; `openf1_historical` pentru reluare.
8. **Ce alternative există?** FastF1 pentru istoricul permis. Alternativele live rămân dezactivate deoarece nu au demonstrat un avantaj accesibil verificat. Instanța publică harsh779 era suspendată.
9. **Care sunt upstream-urile?** Formula 1 SignalR/timing files, OpenF1 REST/archive, Jolpica pentru rezultate publicate. Clienții SignalR comparați se bazează în mare parte pe aceeași sursă; nu sunt măsurători independente.
10. **Ce canale funcționează?** TimingData, TimingAppData, TimingStats, DriverList, SessionInfo/Status, WeatherData, RaceControlMessages, TrackStatus și LapCount au fost recepționate în snapshot-ul public de după sesiune. Datele istorice și procesarea protocolului au fost testate separat.
11. **Ce canale lipsesc?** În proba publică actuală nu s-au primit Position.z și CarData.z. Diagnosticele le marchează MISSING, independent de existența unei conexiuni.
12. **Se primesc X/Y live?** Nu a fost observat un flux X/Y într-o sesiune activă în această verificare. Decodorul și consumatorul sunt implementate/testate pe fixture; coordonatele reale au fost verificate doar istoric.
13. **Se primește CarData live?** Nu în proba efectuată. Datele istorice Speed/Gear/Throttle/Brake/DRS/RPM au fost validate prin FastF1; coloanele vechi rămân compatibile.
14. **Se poate afișa fiecare pilot pe circuit?** Da, în reluările cu coordonate. Live doar pentru piloții cu eșantioane X/Y efectiv primite; lipsa acestora nu produce mișcare fictivă. Harta statică poate rămâne vizibilă.
15. **Timing tower funcționează?** Da în reluări și fixture-uri; snapshot-ul public are ordine/timpi reali. LIVE este afișat doar după observații proaspete datate, cu identitate verificată. S-au adăugat tur și opriri observate.
16. **Vremea funcționează?** Da pentru observații valide. Live include limite numerice și provenance per câmp; datele vechi nu devin proaspete prin actualizarea unui alt câmp. Lipsa ploii nu este echivalentă cu asfalt uscat.
17. **Pneurile funcționează?** Compound/TotalLaps/StartLaps păstrează semantica sursei. Uzura rămâne o estimare pentru set, fără patru senzori inventați. Istoricul stinturilor incomplet este marcat explicit.
18. **Race Control funcționează?** Da: mesaje/steaguri, identificatori și pilot, întreruperi/intermisii, ștergere/reintroducere de timpi, incidente raportate. Deteriorarea fizică nemăsurată rămâne necunoscută.
19. **Proiecția campionatului funcționează?** Da, provizoriu, pentru piloți și constructori. Rezultatele GP anterioare și Sprint confirmat intră o singură dată. Modul full-distance este o ipoteză vizibilă; stopped-now refuză să inventeze eligibilitatea dacă lipsesc distanța și tururile verzi. Punctele oficiale nu sunt modificate.
20. **Ce latență s-a măsurat?** Aproximativ 37 ms mediană / 47 ms p95 pentru 20 răspunsuri HTTP locale cu reluare/proiecție. Nu s-a măsurat latența transmisiunii live: snapshot-urile primite nu aveau timestamp de observație verificat. Vezi [performanța](LIVE_PERFORMANCE.md).
21. **Ce se întâmplă la întrerupere?** STALE/RECONNECTING, backoff cu jitter și buget finit. 401/403 oprește accesul. Nu există loop infinit de reconectare sau conexiuni paralele duplicate. Observațiile vechi își păstrează timestamp-urile.
22. **Ce funcționează offline?** Reluările deja descărcate, telemetria deja salvată, datele/rezultatele locale și checkpoint-urile STALE. Descărcarea unei sesiuni noi și primirea live cer rețea.
23. **Ce este verificat doar în replay?** Poziții reale X/Y, telemetria completă/RPM și comportamentul vizual continuu la 30×. Nu sunt redenumite date live.
24. **Ce s-a testat cu surse reale?** Reluări Singapore FP1/SQ/Sprint/Q și GP anterior; două GP OpenF1 2024 pentru evaluare; FastF1 Abu Dhabi 2024; negociere/snapshot public Formula 1 după Singapore GP; endpoint-uri alternative publice. Browser-ul a folosit arhive reale, fără GPS simulat.
25. **Ce nu este validat?** Recepție continuă într-o sesiune activă, reconectare după o întrerupere reală a upstream-ului în timpul cursei și disponibilitatea live Position.z/CarData.z. Aceste cazuri au teste offline, nu dovezi de acces live.
26. **Ce teste au trecut?** 159 backend, 32 Java și 9 ale animației; browser pentru reluare/intermisii/30×, diagnostic/proiecție și layout 320/390/768/1440/1920 px, fără erori JavaScript; test de 202.500 actualizări cu buffere limitate; 20 cutoff-uri istorice. Rapoartele verificabile sunt legate în documentație.
27. **Ce a eșuat?** Inițial au apărut un stint istoric cu lap_start null, indexarea sectoarelor cu goluri și un caz de timestamp rotunjit în test; acestea au fost corectate. Testele de browser au necesitat corectarea așteptării pentru 23 participanți în sezon și a citirii textului pliabil/scroll-ului sub navbar. Nicio astfel de eroare nu este păstrată ca succes. Un test opțional Selenium pentru cote este sărit; live activ este PENDING, iar endpoint-ul alternativ suspendat este UNAVAILABLE. Strategia v1 are rezultate modeste, păstrate integral în raport.
28. **Cum pornesc?** Din root: `backend-python/.venv/bin/python backend-python/app.py`; separat: `mvn -f frontend-java/frontend-java/pom.xml spring-boot:run`. Interfața este pe http://127.0.0.1:8090/race-control. Nu este nevoie de cont plătit pentru arhivele testate.
29. **Cum verific?** `backend-python/.venv/bin/python -m pytest backend-python/tests -q`; `mvn -f frontend-java/frontend-java/pom.xml test`; `node --test scripts/tests/race-control-engine.test.js`; scripturile verify_timing_integration.py, verify_timing_buffers.py, verify_live_sources.py și backtest_race_strategy.py. Comenzile detaliate sunt în celelalte documente și README.
30. **Ce fac la următoarea cursă?** Tools → Update all sessions; aleg sesiunea exactă în Race Control; Start live după ora publicată; deschid Feed diagnostics și urmăresc TimingData datat/identitate VERIFIED. Verific separat Position.z și CarData.z: numai recepția lor reală validează harta/telemetria live. Pentru proba CLI opresc întâi conexiunea aplicației și rulez verify_live_sources cu race ID/cod actual. Dacă apare ACCESS_DENIED sau lipsesc canale, nu încerc ocolirea; folosesc timing-ul permis sau reluarea ulterioară. Salvez raportul real și verific ulterior întreruperea/reconectarea într-o sesiune activă.

Evaluarea strategiei este în [LIVE_BACKTESTING.md](LIVE_BACKTESTING.md). Limitările sunt în [LIVE_LIMITATIONS.md](LIVE_LIMITATIONS.md). Probe: [surse](LIVE_SOURCE_VERIFICATION.json), [FastF1](FASTF1_ARCHIVE_VERIFICATION.json), [browser](LIVE_BROWSER_VERIFICATION.json), [buffere](LIVE_BUFFER_VERIFICATION.json), [benchmark](LIVE_BACKTEST_RESULTS.json).


## Fișiere modificate

- `README.md`
- `backend-python/.env.example`
- `backend-python/api/race_control_routes.py`
- `backend-python/app.py`
- `backend-python/data_sources/public_timing_provider.py`
- `backend-python/data_sources/race_control_sources.py`
- `backend-python/data_sources/timing_contract.py`
- `backend-python/requirements.txt`
- `backend-python/services/race_control_checkpoint.py`
- `backend-python/services/race_control_projection_service.py`
- `backend-python/services/race_control_service.py`
- `backend-python/services/race_strategy_service.py`
- `backend-python/tests/test_race_control.py`
- `backend-python/tests/test_timing_integration.py`
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/FASTF1_ARCHIVE_VERIFICATION.json`
- `docs/KNOWN_LIMITATIONS.md`
- `docs/LIVE_BACKTESTING.md`
- `docs/LIVE_BACKTEST_RESULTS.json`
- `docs/LIVE_BROWSER_VERIFICATION.json`
- `docs/LIVE_BUFFER_VERIFICATION.json`
- `docs/LIVE_CONNECTION_LIFECYCLE.md`
- `docs/LIVE_DATA_ARCHITECTURE.md`
- `docs/LIVE_DATA_SCHEMA.md`
- `docs/LIVE_DIAGNOSTICS.md`
- `docs/LIVE_FEED_AUDIT.md`
- `docs/LIVE_INTEGRATION_REPORT.md`
- `docs/LIVE_INTEGRATION_VERIFICATION.json`
- `docs/LIVE_LIMITATIONS.md`
- `docs/LIVE_PERFORMANCE.md`
- `docs/LIVE_PROVIDER_AUDIT.json`
- `docs/LIVE_PROVIDER_COMPARISON.md`
- `docs/LIVE_SOURCE_VERIFICATION.json`
- `docs/RACE_CONTROL.md`
- `docs/RACE_STRATEGY.md`
- `docs/RACE_STRATEGY_VERIFICATION.json`
- `docs/RUNBOOK.md`
- `docs/TESTING.md`
- `docs/THESIS_NOTES.md`
- `docs/VERIFIED_DEPENDENCIES.json`
- `docs/screenshots/race-control-smooth-map.png`
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
- `scripts/verify_live_sources.py`
- `scripts/verify_race_control_strategy.py`
- `scripts/verify_timing_buffers.py`
- `scripts/verify_timing_integration.py`

Verificare de pornire, pagini, rezultate oficiale și regresii: [LIVE_INTEGRATION_VERIFICATION.json](LIVE_INTEGRATION_VERIFICATION.json). Modificările News din timpul verificării provin din scheduler-ul existent, păstrat; nicio clasificare sau tabel oficial nu a fost rescris de această integrare.
