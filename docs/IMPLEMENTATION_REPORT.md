# Raport de implementare — F1 Predictor

Verificare locală: 8 octombrie 2026. Sursa de adevăr a fost directorul existent, fără `.git`; nu s-a înlocuit proiectul cu o versiune GitHub. Comenzile și rapoartele de mai jos disting funcțiile rulate de integrările neconfigurate.

## 1. Constatări ale auditului

Importul ignora paginarea și lăsa exact 100 de rezultate/sezon. Toate cele 216 curse inițiale erau marcate încheiate: 165 fără rezultate, 7 viitoare. Anul curent era fixat la 2025. Clasamentele cumulau sezoane. Ambele ramuri de predicție foloseau rezultate ale cursei țintă și informație viitoare; „ML” era o formulă euristică. Lipseau validarea temporală, modelele antrenate, metricile, timestampurile cotelor, paginile generice de detaliu și testele backend. Audit complet: [CURRENT_STATE_AUDIT.md](CURRENT_STATE_AUDIT.md).

## 2. Baza de date

Backup SQLite consistent înainte de migrare și arhivă a surselor originale în `database/backups`. Migrare aditivă versiunea 1, fără ștergerea istoricului sau schimbarea identificatorilor. S-au adăugat status/proveniență/verificare și timestampuri de sesiune pentru curse, plus ture/durată/tur rapid pentru rezultate. Tabele noi: race_entries, qualifying_results, sprint_results, standing_snapshots, data_sync_runs, prediction_runs, odds_snapshots, driver_media, session_data, model_metrics, explanation_cache, schema_migrations.

Chei unice, verificări de referințe și protecție la ștergerea datelor asociate. Schema SQL de referință a fost corectată și executată într-o bază temporară. După completarea istoricului: **275 de curse, 5.457 de rezultate, 2014–2026**. Raportul de calitate nu semnalează probleme în verificările implementate. Repetarea sincronizării nu modifică numărul curselor, rezultatelor sau participărilor; actualizarea timestampului celor două snapshoturi de clasament este normală.

## 3. Surse de date

Jolpica furnizează identități, calendar, rezultate, calificări, sprinturi și clasamente, prin paginare, cache, retry și upsert atomic. FastF1 adaugă sesiuni/meteo la cerere: test live cu 22 rezultate și 254 eșantioane meteo pentru ultima cursă, fără telemetrie. OpenF1 a actualizat portretele/culorile a 22 piloți din ultima sesiune încheiată. Selenium are responsabilitatea exclusivă de a citi cote publice, când este configurat. Detalii și verificarea cu paginile oficiale Formula 1: [DATA_PIPELINE.md](DATA_PIPELINE.md).

La snapshotul verificat: sezon 2026, ultima cursă Bahrain Grand Prix in Malaysia din 4 octombrie, câștigător Max Verstappen; următoarea Singapore, 11 octombrie. Aceste valori nu sunt codate în producție.

## 4. Modelul predictiv

32 de caracteristici: formă pe ferestre 3/5/10, experiență, puncte/rang înaintea cursei, fiabilitate, constructor, circuit, calificări când sunt cunoscute și context de sezon. Regresie logistică scalată cu clasificatori separați pentru victorie, podium și top zece; calibrare sigmoidă pe un sezon distinct. Baseline euristic explicit și benchmark HistGradientBoosting. Producție: antrenare 2014–2024, calibrare 2025. Campionat: simulare Monte Carlo cu 5.000 iterații implicit, puncte oficiale actuale, curse/sprinturi rămase și abandonuri simulate.

## 5. Prevenirea leakage-ului

Fiecare predicție are feature_cutoff, training_cutoff, mod și versiune. PRE_WEEKEND oprește istoricul la începutul weekendului; POST_QUALIFYING permite numai calificări disponibile înaintea pragului. Rezultatele precedente au un buffer temporal; cursa țintă și viitorul sunt excluse din agregări. Modelul încărcat trebuie să fi fost antrenat pe date anterioare pragului. Rezultatele țintă sunt doar etichete de evaluare. Testul critic modifică poziție/puncte/status/grilă și rezultate viitoare fără să schimbe predicția pre-weekend. Replay-urile istorice nu sunt numite predicții prospective. Corecțiile istorice finale și rosterul reconstruit rămân limite explicite.

## 6. Metrici reale

Evaluare walk-forward pe **92 de curse din 2022–2025**:

| Mod / model | Top 1 | Câștigător în Top 3 | MAE | Brier | Log loss/cursă |
|---|---:|---:|---:|---:|---:|
| Pre-weekend baseline | 45,65% | 72,83% | 3,894 | 0,03642 | 1,6868 |
| Pre-weekend logistic | 50,00% | 79,35% | 3,891 | 0,03415 | 1,6388 |
| După calificări baseline | 53,26% | 81,52% | 3,551 | 0,03247 | 1,4413 |
| După calificări logistic | 51,09% | 85,87% | 3,272 | 0,03000 | 1,3056 |

Logistic nu este superior la toate metricile: Top 1 după calificări și ECE sunt sub nivelul baseline-ului. [MODEL_CARD.md](MODEL_CARD.md) conține toate metricile, inclusiv Spearman, precizie/recall podium, ECE, benchmarkul boosting, fiecare fold și datele antrenării. Fișierele JSON măsurate se află în `docs/evaluation`. Nu există rezultate ML+cote inventate.

## 7. Cote

Funcționează furnizorul manual, validarea cotelor/identităților, eliminarea marjei, agregarea mai multor surse și amestecul opțional. Lipsa cotelor lasă modelul neschimbat; cărțile incomplete nu anulează șansele piloților fără cote. Sunt validate timestampurile individuale, nu doar data lotului. Selenium: test Chrome real pe fixture local, inclusiv parsare și cleanup. **Niciun bookmaker real configurat/verificat.** Ultima verificare: 8 octombrie 2026. [ODDS_AND_SELENIUM.md](ODDS_AND_SELENIUM.md).

## 8. LLM

Explică numere deja calculate și rezultate confirmate prin OpenAI Responses API, la cerere și cu cache. Variabile: `LLM_ENABLED`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_CACHE_ENABLED`. Modelul nu este hardcodat. Fallback RO/EN la dezactivare, lipsă cheie/model sau eroare; testat. SDK instalat. **Apel live netestat: nu există cheie configurată.** [LLM_INTEGRATION.md](LLM_INTEGRATION.md).

## 9. Frontend

Dashboard orientat pe ultima cursă, câștigător generic, următoarea cursă, favorit și performanța modelului. Pagini noi pentru cursă/pilot, campionat separat de clasamentul oficial, selecție sezon/cursă/mod, carduri Top 3, explicații, file MODEL/MARKET/COMBINED, date/joburi și metodologie. Portrete din sursă cu fallback SVG, culori de echipă, dark/light și responsive 390 px. Animațiile respectă prefers-reduced-motion. S-au păstrat rutele CRUD, importul, forma, scenariile/regulamentele, istoricul și exportul. Testul de randare folosește un câștigător arbitrar, fără condiții speciale pentru numele pilotului.

## 10. Fișiere create

Lista integrală a fișierelor sursă, configurație, teste și documentație se găsește în [CHANGED_FILES.md](CHANGED_FILES.md), secțiunea Created, și în [CHANGE_MANIFEST.json](CHANGE_MANIFEST.json). Inventarul este calculat față de hashurile din audit; exclude mediile virtuale, cache-urile, dependențele compilate și secretele.

## 11. Fișiere modificate

Lista integrală este în [CHANGED_FILES.md](CHANGED_FILES.md), secțiunea Modified. Datele SQLite, snapshoturile, modelele/dataseturile generate, setările locale și backupurile sunt descrise separat acolo. Nu s-a creat commit, deoarece directorul primit nu este un repository Git.

## 12. Comenzi backend

Din rădăcina proiectului:

```sh
python3 -m venv backend-python/.venv
backend-python/.venv/bin/python -m pip install -r backend-python/requirements-dev.txt
backend-python/.venv/bin/python scripts/backup_database.py
backend-python/.venv/bin/python scripts/migrate_database.py
backend-python/.venv/bin/python backend-python/app.py
```

Mediul virtual local este deja instalat. Pe un checkout fără DB se omite backupul inițial. Se copiază `.env.example` în `.env` numai dacă nu există configurație locală. Pentru LLM se instalează separat `requirements-llm.txt`.

## 13. Comenzi frontend

```sh
cd frontend-java/frontend-java
mvn spring-boot:run
```

Build din rădăcină:

```sh
mvn -f frontend-java/frontend-java/pom.xml test package
java -jar frontend-java/frontend-java/target/frontend-java-0.0.1-SNAPSHOT.jar
```

## 14. Comenzi sincronizare

```sh
backend-python/.venv/bin/python scripts/sync_f1_data.py --current
backend-python/.venv/bin/python scripts/sync_f1_data.py --season 2025
backend-python/.venv/bin/python scripts/sync_f1_data.py --from 2014 --to "$(date +%Y)"
backend-python/.venv/bin/python scripts/data_quality_report.py
```

## 15. Comenzi modele

```sh
backend-python/.venv/bin/python scripts/build_training_dataset.py --mode PRE_WEEKEND
backend-python/.venv/bin/python scripts/train_models.py --through-season 2025 --mode PRE_WEEKEND
backend-python/.venv/bin/python scripts/train_models.py --through-season 2025 --mode POST_QUALIFYING
backend-python/.venv/bin/python scripts/evaluate_models.py --season 2025 --mode PRE_WEEKEND
```

Anul explicit reproduce experimentul raportat; implicit antrenarea folosește ultimul an calendaristic încheiat.

## 16. Teste și verificare

```sh
backend-python/.venv/bin/python -m pytest backend-python/tests -q
RUN_SELENIUM=1 backend-python/.venv/bin/python -m pytest backend-python/tests/test_odds_parser.py -q
mvn -f frontend-java/frontend-java/pom.xml test package
backend-python/.venv/bin/python scripts/verify_running_app.py --browser
```

Rezultate: **41 teste backend trecute**, un test Chrome opțional omis în rularea implicită; separat **3 teste Selenium trecute** cu Chrome real; **10 teste Java trecute**, JAR construit. E2E: 18 pagini GET, șase acțiuni POST frontend, predicții fără/pentru cote manuale, probabilități valide, simulare 500 iterații prin API și 5.000 prin UI, fallback LLM, winner hero, RO/EN, teme și mobil. Capturile au fost inspectate vizual. Cele cinci exporturi CSV/TXT au returnat HTTP 200 și conținut valid; răspunsul 404 pentru o entitate inexistentă respectă schema de eroare. Rapoarte: [E2E](E2E_VERIFICATION.json), [sync](SYNC_VERIFICATION.json), [calitate](DATA_QUALITY_REPORT.json), [versiuni](VERIFIED_DEPENDENCIES.json).

## 17. URL-uri utile

| Funcție | URL |
|---|---|
| Aplicație | http://127.0.0.1:8090/ |
| Predicții | http://127.0.0.1:8090/predictions |
| Campionat | http://127.0.0.1:8090/championship |
| Date / sincronizare | http://127.0.0.1:8090/data |
| Metodologie | http://127.0.0.1:8090/model |
| Clasamente | http://127.0.0.1:8090/standings |
| Piloți / curse | http://127.0.0.1:8090/drivers · http://127.0.0.1:8090/races |
| Ultima cursă din snapshot | http://127.0.0.1:8090/races/209 |
| Simulator / regulamente | http://127.0.0.1:8090/simulator · http://127.0.0.1:8090/regulations |
| Istoric / export | http://127.0.0.1:8090/history · http://127.0.0.1:8090/export |
| Health API | http://127.0.0.1:5000/health |
| Context / metrici | http://127.0.0.1:5000/season/context · http://127.0.0.1:5000/model/metrics |

## 18. Limitări rămase

Fără furnizor bookmaker real sau arhivă pentru evaluare ML+cote; fără test LLM live fără cheie. POST_PRACTICE nu are caracteristici/model antrenat; grila finală, strategia, telemetria și meteo nu intră în modelul factual. Calibrarea nu este perfectă. Replay-ul folosește date corectate și roster reconstruit. Scenariile sunt ipoteze de sensibilitate, nu efecte cauzale. Campionatul presupune formă constantă, abandonuri independente și punctaj integral. Portretele pot avea rezoluție mică, iar media reflectă ultima sesiune, nu aspectul istoric. Traducerea acoperă navigația și etichetele principale; unele explicații rămân în engleză. Export PDF opțional neimplementat. Joburile sunt locale și nu supraviețuiesc restartului. Este o aplicație locală de cercetare, fără autentificare multi-user sau infrastructură de producție.

## 19. Explicație pentru coordonator

„Proiectul separă achiziția și stocarea datelor Formula 1 de calculul probabilităților și prezentarea lor. Am eliminat folosirea rezultatului cursei țintă în predicție și am introdus validare cronologică, calibrare și comparație cu un baseline. Pe 92 de curse de test, modelul logistic identifică pre-weekend câștigătorul în 50% dintre cazuri, față de 45,7% pentru baseline. Aplicația permite auditarea datelor, simularea campionatului și explicarea estimărilor, iar limitele statistice și ale surselor sunt documentate.”

Explicația extinsă și direcțiile de cercetare sunt în [THESIS_NOTES.md](THESIS_NOTES.md).

## Corecție după verificarea utilizatorului

Modul After qualifying pentru Singapore era respins corect de backend, dar validarea 400 era afișată greșit ca eroare de serviciu 503. Interfața verifică acum disponibilitatea reală a calificărilor, dezactivează opțiunea indisponibilă și păstrează formularul și cotele la validări. Mesajul oferă Pre-weekend fără a rula automat alt model. Un endpoint read-only folosește același prag temporal ca predicția; protecția contra leakage rămâne activă. Au fost adăugate teste pentru cazul raportat, disponibilitate, valori păstrate și erori reale de serviciu.
