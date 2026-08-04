# Opsætning

## 1. Lokal kontrol

Installer Python-dependency og generér kalenderen:

```bash
python -m pip install -r requirements.txt
python generate_calendar.py
```

Åbn `calendar/have.ics` i en teksteditor og kontrollér, at filen starter med `BEGIN:VCALENDAR`.

## 2. Tilpasning

De vigtigste valg ligger øverst i `garden.yaml`:

- `generation_months_before`: hvor mange måneder kalenderen starter før genereringstidspunktet, normalt 1
- `alarm_days_before`: påmindelse før hver opgave
- `bed4_mode`: `leeks` eller `bush_beans`
- `optional_pea_hold_7`: slå den ekstra juli-såning af eller på
- `selected_event_ids`: hvilke opgavetyper der faktisk kommer med i abonnementet

Vejrindstillingerne ligger i `weather`:

- `postal_code`: havens postnummer, her 5485
- `forecast_days`: Open-Meteo-prognosens længde, højst 16 dage
- `max_shift_days`: maksimal fremflytning af en vejrrelevant opgave
- `extra_outdoor_watering`: ekstra vandingspåmindelser for udendørs bede ved tørke
- `greenhouse_extra_watering`: skal være `false`; drivhuset får ikke regnbaserede vandingsevents

Kalenderen er med vilje begrænset. Den indeholder alle så-, forspirings- og planteopgaver samt hvidløgshøst, gødning af drivhusplanter, nedklipning af honningurt og vinterrug, vinterklargøring, majshøst og høstvinduer for spinat, rødbeder og porrer. Der er ikke længere faste påmindelser om udluftning, vand, sideskud eller høst af tomater, agurker, peber og ærter.

Hver opgave har blandt andet `action`, `crop`, `location`, `note`, `start`, `end` og eventuelt `repeat_days`. Datoer skrives som `MM-DD`.

## 3. GitHub Actions

Workflowet `.github/workflows/update.yml`:

1. kan startes med `workflow_dispatch`
2. kører automatisk dagligt kl. 02:17 UTC
3. installerer `requirements.txt`
4. genererer `calendar/have.ics`
5. committer og pusher kun, hvis filen har ændret sig

Ved hver generering hentes en kort Open-Meteo-prognose. Udendørs så- og planteopgaver samt de valgte udendørs høstvinduer kan flyttes nogle få dage frem ved kraftig regn, kulde eller frost. Den oprindelige planlagte dato bruges i eventets UID, så en flytning opdaterer abonnementseventet i stedet for at skabe en dublet. Ved API-fejl falder generatoren tilbage til kalenderens normale datoer.

Repositoryets Actions skal have skriveadgang til indhold. Det er sat med `permissions: contents: write` i workflowet.

## 4. GitHub Pages

Under **Settings → Pages** vælger du deployment fra branch `main` og mappen `/ (root)`. Når Pages er aktiv, skal `calendar/have.ics` kunne åbnes på repositoryets Pages-domæne.

På GitHub Free er Pages begrænset til offentlige repositories. GitHub Pro, Team og Enterprise kan bruge et privat source-repository, men den publicerede side er normalt offentligt tilgængelig. En reelt privat Pages-side kræver GitHub Enterprise Cloud for en organisation. Denne kalender indeholder kun haveopgaver og ingen følsomme oplysninger.

En iPhone-abonnementskalender skal kunne hente `.ics`-filen uden en interaktiv GitHub-login, så test URL'en i et privat browser-vindue før abonnement.
