# Havekalender

En lille privat havekalender til en dansk køkkenhave. Projektet genererer en statisk `calendar/have.ics`, som kan udgives via GitHub Pages og abonneres på fra iPhone Kalender.

## Indhold

- YAML-konfiguration i [`garden.yaml`](garden.yaml)
- Python-generator uden tungt framework
- Deterministiske UID'er, så abonnementet ikke får dubletter ved nye genereringer
- Heldagsbegivenheder med 2-dages påmindelse
- Løbende såning af ærter i langbedet
- Drivhus, bedrotation, porrer/buskbønner, companion planting og grøngødning
- GitHub Actions, der kan køres manuelt og automatisk hver nat

## Lokal generering

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python generate_calendar.py
```

Outputtet er [`calendar/have.ics`](calendar/have.ics).

`garden.yaml` genererer som standard et rullende vindue på 10 år. Det starter i 2026 og flytter sig automatisk frem, når kalenderåret skifter. Bed 4 bruger porrer; skift `bed4_mode` til `bush_beans` for buskbønner.

## GitHub Pages

Slå GitHub Pages til for repositoryet med `main` som branch og `/ (root)` som mappe. Den forventede abonnement-URL er:

```text
https://JondareHM.github.io/garden-calendar/calendar/have.ics
```

Kontrollér den faktiske URL under repositoryets Pages-indstillinger. Hvis privat GitHub Pages ikke er tilgængelig på kontoen, skal kun selve kalenderfilen hostes et sted, hvor iPhone kan hente den uden login.

GitHub Pages kan bruge et privat source-repository på GitHub Pro, Team eller Enterprise, men den publicerede side er normalt offentligt tilgængelig. En reelt privat Pages-side kræver GitHub Enterprise Cloud for en organisation. Kalenderen indeholder derfor kun haveopgaver og ingen følsomme oplysninger.

Se også [Setup](docs/Setup.md) og [iPhone-guide](docs/iPhone.md).
