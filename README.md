# Havekalender

En lille privat havekalender til en dansk køkkenhave. Projektet genererer en statisk `calendar/have.ics`, som kan udgives via GitHub Pages og abonneres på fra iPhone Kalender.

## Indhold

- YAML-konfiguration i [`garden.yaml`](garden.yaml)
- Python-generator uden tungt framework
- Deterministiske UID'er, så abonnementet ikke får dubletter ved nye genereringer
- Heldagsbegivenheder med 2-dages påmindelse
- Bevidst begrænset til såning, forspiring, udplantning, udvalgte jordopgaver og høstvejledning for spinat, rødbeder og porrer
- Løbende såning af ærter i langbedet
- Drivhus, bedrotation, porrer/buskbønner, companion planting og grøngødning
- Open-Meteo-vejrtilpasning for nært forestående udendørs opgaver ved postnummer 5485
- Højst én ekstra tørke-/vandingspåmindelse pr. udendørs tørkeperiode; drivhuset får ingen regnbaseret vandingsevent
- GitHub Actions, der kan køres manuelt og automatisk hver nat

## Lokal generering

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python generate_calendar.py
```

Outputtet er [`calendar/have.ics`](calendar/have.ics) samt den korte, visuelt grupperede Pages-oversigt [`index.html`](index.html).

`garden.yaml` genererer ét rullende år ad gangen. Vinduet starter én måned før genereringstidspunktet og flytter sig dagligt. Bed 4 bruger porrer; skift `bed4_mode` til `bush_beans` for buskbønner.

Vejrprognosen hentes gratis fra Open-Meteo uden API-nøgle. Kun opgaver inden for prognosen kan flyttes, og de flyttes højst fem dage frem. Indendørs opgaver flyttes ikke. Udplantning i drivhuset vurderes på kulde/frost, mens regn ikke bruges til drivhusvanding. Hvis API'et er utilgængeligt, beholdes de faste datoer.

## GitHub Pages

Slå GitHub Pages til for repositoryet med `main` som branch og `/ (root)` som mappe. Den forventede abonnement-URL er:

```text
https://JondareHM.github.io/garden-calendar/calendar/have.ics
```

Kontrollér den faktiske URL under repositoryets Pages-indstillinger. Hvis privat GitHub Pages ikke er tilgængelig på kontoen, skal kun selve kalenderfilen hostes et sted, hvor iPhone kan hente den uden login.

Pages-forsiden viser de store opgaver pr. bed. Den genereres automatisk sammen med kalenderen og følger derfor det aktuelle rullende år samt eventuelle vejrtilpasninger.

Så-, plante- og høstevents indeholder også en kort `Hvornår`-note med de forhold, der bør afgøre den faktiske dato. På Pages-oversigten kan noten åbnes pr. event; i kalenderabonnementet står den i eventets beskrivelse. En eventuel `timing_note` i YAML kan bruges til at overskrive den automatiske tekst.

GitHub Pages kan bruge et privat source-repository på GitHub Pro, Team eller Enterprise, men den publicerede side er normalt offentligt tilgængelig. En reelt privat Pages-side kræver GitHub Enterprise Cloud for en organisation. Kalenderen indeholder derfor kun haveopgaver og ingen følsomme oplysninger.

Se også [Setup](docs/Setup.md) og [iPhone-guide](docs/iPhone.md).
