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

- `first_year`: første år i kalenderen, her 2026
- `years_ahead`: antal år der genereres frem
- `alarm_days_before`: påmindelse før hver opgave
- `bed4_mode`: `leeks` eller `bush_beans`
- `optional_pea_hold_7`: slå den ekstra juli-såning af eller på

Hver opgave har blandt andet `action`, `crop`, `location`, `note`, `start`, `end` og eventuelt `repeat_days`. Datoer skrives som `MM-DD`.

## 3. GitHub Actions

Workflowet `.github/workflows/update.yml`:

1. kan startes med `workflow_dispatch`
2. kører automatisk dagligt kl. 02:17 UTC
3. installerer `requirements.txt`
4. genererer `calendar/have.ics`
5. committer og pusher kun, hvis filen har ændret sig

Repositoryets Actions skal have skriveadgang til indhold. Det er sat med `permissions: contents: write` i workflowet.

## 4. GitHub Pages

Under **Settings → Pages** vælger du deployment fra branch `main` og mappen `/ (root)`. Når Pages er aktiv, skal `calendar/have.ics` kunne åbnes på repositoryets Pages-domæne.

På GitHub Free er Pages begrænset til offentlige repositories. GitHub Pro, Team og Enterprise kan bruge et privat source-repository, men den publicerede side er normalt offentligt tilgængelig. En reelt privat Pages-side kræver GitHub Enterprise Cloud for en organisation. Denne kalender indeholder kun haveopgaver og ingen følsomme oplysninger.

En iPhone-abonnementskalender skal kunne hente `.ics`-filen uden en interaktiv GitHub-login, så test URL'en i et privat browser-vindue før abonnement.
