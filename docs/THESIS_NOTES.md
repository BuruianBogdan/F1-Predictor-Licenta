# Note pentru lucrarea de licență

## Problema și contribuția

F1 Predictor estimează probabilități pentru curse și campionat și prezintă utilizatorului datele care susțin estimările. Problema nu este doar alegerea unui algoritm: informația trebuie sincronizată complet, asociată sezonului corect și disponibilă înainte de evenimentul prezis. Versiunea inițială folosea rezultate ale aceleiași curse ca intrări, ceea ce producea data leakage și făcea imposibilă o evaluare credibilă.

Contribuția proiectului este o arhitectură verificabilă, de la surse până la predicții, cu praguri temporale, jurnalizarea operațiilor, comparație cu un model de referință și evaluare pe sezoane viitoare față de antrenare. Interfața explică rezultatele și incertitudinea fără să prezinte o probabilitate drept certitudine.

## Arhitectură și achiziție

Backendul Flask folosește SQLAlchemy și SQLite; frontendul Spring Boot/Thymeleaf consumă REST. Jolpica furnizează calendarul, participanții, rezultatele, calificările, sprinturile și clasamentele. Sincronizarea paginată face upsert și este atomică pe sezon. FastF1 adaugă explicit date de sesiune/meteo, iar OpenF1 portrete. Se păstrează separat identitatea pilotului și participarea sa la o cursă pentru a modela transferurile între echipe.

Baza verificată conține 275 de curse și 5.457 de rezultate pentru 2014–2026. Migrarea a păstrat istoricul și identificatorii; copia de siguranță permite recuperarea. O cursă este încheiată numai după rezultate validate, nu doar fiindcă data programată a trecut.

## Feature engineering și algoritmi

Cele 32 de caracteristici descriu forma recentă a pilotului, punctele și poziția înaintea cursei, fiabilitatea, performanța constructorului, istoricul pe circuit și contextul sezonului. Calificările sunt disponibile doar în modul corespunzător. Nu sunt utilizate poziția finală, punctele, statutul sau grila finală extrase din rezultatul cursei țintă.

Se compară un baseline euristic, regresie logistică și HistGradientBoosting. Regresia logistică antrenează clasificatori pentru victorie, podium și clasare în primii zece. Calibrarea sigmoidă folosește un sezon ulterior și distinct de antrenare. Probabilitățile de victorie sunt normalizate pe grilă; clasificarea rezultată se evaluează după această transformare.

## Validare temporală și rezultate

Nu există împărțire aleatoare a curselor. Pentru testul 2022, se antrenează pe 2014–2020 și se calibrează pe 2021; fereastra avansează anual până în 2025. Cele patru sezoane de test conțin 92 de curse. Modelul de producție se antrenează pe 2014–2024 și se calibrează pe 2025.

Înainte de weekend, acuratețea Top 1 este 50,00% pentru modelul logistic și 45,65% pentru baseline; includerea câștigătorului în primii trei crește de la 72,83% la 79,35%. Brier scade de la 0,03642 la 0,03415. După calificări, modelul logistic are MAE 3,272 și Brier 0,03000, însă acuratețea Top 1 de 51,09% este sub baseline-ul de 53,26%. ECE nu este mai bun decât baseline-ul. Aceste limite sunt rezultate ale cercetării, nu trebuie ascunse.

Un test de regresie modifică rezultatele țintă și viitoare și demonstrează că intrările și predicția pre-weekend nu se schimbă. Totuși, arhiva conține corecții finale și liste de participanți reconstruite: nu afirmăm că avem toate informațiile exact în forma publicată istoric. Pentru o validare mai strictă ar trebui colectate snapshoturi prospective.

## Campionat, cote și LLM

Campionatul este simulat Monte Carlo de 5.000 de ori, pornind de la punctele oficiale actuale și calendarul rămas. Sunt incluse sprinturile și abandonurile simulate, cu ipoteze documentate și seed fix.

Cotele zecimale se transformă în probabilități, se elimină marja și se combină opțional cu modelul. Timestampurile trebuie să precede pragul predicției. Selenium are doar rol de achiziție; testele folosesc o pagină locală. Nu există furnizor real de pariuri configurat sau rezultate istorice ML+cote fără o arhivă de cote.

LLM-ul explică probabilitățile deja calculate și rezultatele confirmate. Nu antrenează modelul și nu decide câștigătorul. Integrarea este opțională, cu cache și text determinist când lipsește cheia sau serviciul este indisponibil. Apelul live nu a fost testat fără cheie API.

## Limite și lucrări viitoare

Direcții relevante pentru licență: arhivă prospectivă cu timp de publicare, experimente de ablație, intervale de încredere prin bootstrap la nivel de cursă, selecție de hiperparametri pe validare interioară, clasificare completă de tip learning-to-rank, calibrare multiclasă după normalizarea grilei, date de antrenamente și strategie, modele separate de fiabilitate și cuantificarea schimbărilor regulamentare.

Scenariile actuale sunt analize de sensibilitate, nu estimări cauzale. Simularea nu anticipează dezvoltarea monoposturilor sau corelația incidentelor. O prezentare academică trebuie să distingă acuratețea retrospectivă de performanța viitoare și disponibilitatea datelor de certitudinea predicției.

## Explicație scurtă pentru coordonator

„Dezvolt o platformă de analiză și predicție Formula 1 care separă achiziția datelor, calculul probabilităților și explicarea rezultatelor. Am corectat utilizarea informațiilor viitoare, am construit un set de caracteristici cu prag temporal și am comparat algoritmii pe patru sezoane de test. Modelul logistic identifică pre-weekend câștigătorul în 50% dintre cele 92 de curse evaluate, față de 45,7% pentru baseline. Lucrarea urmărește reproductibilitatea și evaluarea onestă, inclusiv situațiile în care modelul nu îmbunătățește rezultatul.”
