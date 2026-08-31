from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
GARDEN_PATH = ROOT / "garden.yaml"
INITIAL_STATE_PATH = ROOT / "initial_state.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False, width=1000)


def event_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {event["id"]: event for event in data.get("events", [])}


def remove_ids(ids: list[str], values: set[str]) -> list[str]:
    return [event_id for event_id in ids if event_id not in values]


def ensure_after(ids: list[str], anchor: str, new_ids: list[str]) -> list[str]:
    ids = [event_id for event_id in ids if event_id not in new_ids]
    insert_at = ids.index(anchor) + 1 if anchor in ids else len(ids)
    return ids[:insert_at] + new_ids + ids[insert_at:]


def upsert_event(events: list[dict[str, Any]], new_event: dict[str, Any], after_id: str | None = None) -> None:
    for index, event in enumerate(events):
        if event.get("id") == new_event["id"]:
            events[index] = new_event
            return

    if after_id:
        for index, event in enumerate(events):
            if event.get("id") == after_id:
                events.insert(index + 1, new_event)
                return

    events.append(new_event)


def update_garden_plan() -> None:
    data = load_yaml(GARDEN_PATH)
    events = data["events"]
    events_by_id = event_map(data)

    maize_ids = {"sow_maize_indoors", "plant_maize_bed2", "harvest_maize_bed2"}
    winter_rye_ids = {"sow_winter_rye", "cut_winter_rye"}

    carrot_ids = ["sow_carrots_bed1", "thin_carrots_bed1", "harvest_carrots_bed1"]
    brussels_ids = [
        "sow_brussels_sprouts_indoors",
        "plant_brussels_sprouts_bed2",
        "harvest_brussels_sprouts_bed2",
    ]

    data["overview_event_ids"] = remove_ids(data["overview_event_ids"], maize_ids | winter_rye_ids)
    data["overview_event_ids"] = ensure_after(data["overview_event_ids"], "harvest_spinach_bed1", carrot_ids)
    data["overview_event_ids"] = ensure_after(data["overview_event_ids"], "sow_early_spinach_bed2", brussels_ids)

    data["selected_event_ids"] = remove_ids(data["selected_event_ids"], maize_ids | winter_rye_ids)
    data["selected_event_ids"] = ensure_after(data["selected_event_ids"], "harvest_spinach_bed1", carrot_ids)
    data["selected_event_ids"] = ensure_after(data["selected_event_ids"], "sow_early_spinach_bed2", brussels_ids)

    for bed in data["beds"]:
        if bed["id"] == "bed1":
            bed["plan"] = "Spinat → gulerødder/rødbeder i delt bed → efterårsspinat eller honningurt"
        elif bed["id"] == "bed2":
            bed["plan"] = "Rosenkål med tidlig spinat i ledige huller"

    events_by_id["sow_early_spinach_bed2"]["note"] = (
        "Så tidlig spinat i ledige huller som forafgrøde, før rosenkålene fylder bedet."
    )

    upsert_event(
        events,
        {
            "id": "sow_carrots_bed1",
            "emoji": "🥕",
            "action": "Så",
            "crop": "gulerødder",
            "location": "Bed 1",
            "note": "Sæt en fast gulerodssektion af efter den tidlige spinat. Del resten af bedet med rødbeder, så begge afgrøder kan nås uden at tage et helt bed hver.",
            "start": "04-15",
            "end": "05-15",
            "repeat_days": 14,
            "weather_mode": "outdoor_sow",
        },
        after_id="harvest_spinach_bed1",
    )
    upsert_event(
        events,
        {
            "id": "thin_carrots_bed1",
            "emoji": "✂️",
            "action": "Udtynd",
            "crop": "gulerødder",
            "location": "Bed 1",
            "note": "Udtynd forsigtigt, når planterne står for tæt. Vand først, hvis jorden er tør, og fjern ukrudt mens planterne er små.",
            "start": "05-15",
            "end": "06-15",
            "repeat_days": 14,
        },
        after_id="sow_carrots_bed1",
    )
    upsert_event(
        events,
        {
            "id": "harvest_carrots_bed1",
            "emoji": "🥕",
            "action": "Høst",
            "crop": "gulerødder",
            "location": "Bed 1",
            "note": "Prøvehøst først. Tag de største, når skuldrene har passende størrelse, og lad resten vokse videre så længe kvaliteten er god.",
            "start": "08-15",
            "end": "10-15",
            "repeat_days": 14,
            "weather_mode": "harvest",
        },
        after_id="thin_carrots_bed1",
    )

    events_by_id["sow_beets_bed1"]["note"] = (
        "Så rødbeder i den anden del af Bed 1, eller i huller efter den tidligste spinat. Hold gulerødder og rødbeder som to tydelige sektioner, så udtynding og høst er nemt."
    )
    events_by_id["sow_autumn_spinach_bed1"]["note"] = (
        "Brug ledige huller efter gulerødder og rødbeder. Hvis større dele ryddes tidligt, kan honningurt vælges i stedet som standard vinterdække."
    )

    upsert_event(
        events,
        {
            "id": "sow_brussels_sprouts_indoors",
            "emoji": "🌱",
            "action": "Forspir",
            "crop": "rosenkål",
            "location": "Bed 2",
            "note": "Forspir få planter til Bed 2. Rosenkål fylder længe, så sigt efter 2-3 stærke planter frem for et helt tæt bed.",
            "start": "03-15",
            "end": "04-01",
            "repeat_days": 14,
        },
        after_id="sow_early_spinach_bed2",
    )
    upsert_event(
        events,
        {
            "id": "plant_brussels_sprouts_bed2",
            "emoji": "🌿",
            "action": "Plant ud",
            "crop": "rosenkål",
            "location": "Bed 2",
            "note": "Plant 2-3 rosenkål langs den ene side af bedet efter hærdning. Brug resten af pladsen til tidlig spinat, indtil rosenkålene fylder mere.",
            "start": "05-01",
            "end": "05-20",
            "repeat_days": 14,
            "weather_mode": "outdoor_plant",
        },
        after_id="sow_brussels_sprouts_indoors",
    )
    upsert_event(
        events,
        {
            "id": "harvest_brussels_sprouts_bed2",
            "emoji": "🥬",
            "action": "Høst",
            "crop": "rosenkål",
            "location": "Bed 2",
            "note": "Høst de nederste faste knopper først og arbejd op ad stokken. Lad planterne stå gennem efterår og tidlig vinter, så længe kvaliteten er god.",
            "start": "10-01",
            "end": "12-15",
            "repeat_days": 14,
            "weather_mode": "harvest",
        },
        after_id="plant_brussels_sprouts_bed2",
    )

    events_by_id = event_map(data)
    events_by_id["sow_phacelia"]["note"] = (
        "Standardvalg på tomme bede fra sensommeren. Prioritér honningurt over vinterrug, især i bede der ryddes i august eller september."
    )
    events_by_id["sow_phacelia"]["end"] = "09-30"
    events_by_id["sow_winter_rye"]["note"] = (
        "Fallback hvis honningurt ikke er mulig, og du faktisk har vinterrug. Ellers brug honningurt tidligt eller kompost/blade som jorddække senere."
    )
    events_by_id["prepare_beds_for_winter"]["note"] = (
        "Fjern syge planter, lad sunde rødder blive hvor muligt, fyld eventuelt kompost på, og dæk bar jord med blade, kompost eller andet jorddække. Brug dette især dér, hvor det er blevet for sent til honningurt."
    )

    write_yaml(GARDEN_PATH, data)


def update_initial_state() -> None:
    data = load_yaml(INITIAL_STATE_PATH)
    events = data["events"]
    by_id = event_map(data)

    replacements = {
        "current_decide_winter_rye_bed2": {
            "id": "current_decide_phacelia_bed2",
            "emoji": "🌾",
            "action": "Så eventuelt",
            "crop": "honningurt i ryddede dele",
            "location": "Bed 2",
            "note": "Prioritér honningurt, hvis større dele af bedet er ryddet inden midt/slut september. Hvis porrerne fortsat fylder, så lad dem stå og brug kompost/blade efter sidste høst i stedet.",
            "start": "2026-09-15",
            "weather_mode": "outdoor_sow",
        },
        "current_decide_winter_rye_bed4": {
            "id": "current_decide_phacelia_bed4",
            "emoji": "🌾",
            "action": "Så eventuelt",
            "crop": "honningurt efter spinat",
            "location": "Bed 4",
            "note": "Prioritér honningurt i dele af bedet, der ryddes tidligt nok. Hvis spinaten fortsætter ind i oktober, så drop såning og brug kompost/blade som vinterdække senere.",
            "start": "2026-09-15",
            "weather_mode": "outdoor_sow",
        },
        "current_decide_winter_rye_long_bed": {
            "id": "current_decide_phacelia_long_bed",
            "emoji": "🌾",
            "action": "Så eventuelt",
            "crop": "honningurt i ledige sektioner",
            "location": "Langbed",
            "note": "Prioritér honningurt i færdige sektioner, der er ryddet tidligt nok. Lad bok choi og spinat fortsætte, hvor de stadig fylder, og brug jorddække efter sidste høst.",
            "start": "2026-09-15",
            "weather_mode": "outdoor_sow",
        },
    }

    for index, event in enumerate(events):
        event_id = event.get("id")
        if event_id in replacements:
            events[index] = replacements[event_id]

    by_id = event_map(data)
    by_id["current_winter_prepare_bed2"]["note"] = (
        "Når de sidste porrer er høstet, fjern ukrudt, tilfør et tyndt lag moden kompost og dæk jorden. Lad eventuel honningurt ligge som vinterdække, hvis den nåede at etablere sig."
    )
    by_id["current_winter_check_bed4"]["crop"] = "honningurt eller bar jord"
    by_id["current_winter_check_bed4"]["note"] = (
        "Lad eventuel honningurt ligge som beskyttelse. Ellers dæk bar jord med kompost og blade eller halm efter sidste spinathøst."
    )
    by_id["current_winter_cover_long_bed"]["note"] = (
        "Lad ærterødder og eventuel honningurt blive. Dæk øvrige ledige sektioner med kompost og blade eller halm."
    )

    write_yaml(INITIAL_STATE_PATH, data)


if __name__ == "__main__":
    update_garden_plan()
    update_initial_state()
