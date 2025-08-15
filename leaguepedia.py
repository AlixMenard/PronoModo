import functools
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from mwrogue.esports_client import EsportsClient

_KNOWN_NAMES = {
    "Nigma Galaxy Male": "NGX",
    "Ninjas in Pyjamas.CN": "NIP",
    "SAW (Portuguese Team)": "SAW",
    "Excel Esports": "GX",
    "Rogue (European Team)": "RGE",
    "Aegis (French Team)": "AEG",
    "GIANTX Academy": "GXP",
    "FC Schalke 04 Esports": "S04",
    "Nameless (French Team)": "NMS",
    "Vikings Esports (2023 Vietnamese Team)": "VKE",
    "LYON (2024 American Team)": "LYON",
    "TALON (Hong Kong Team)": "TLN",
    "Gamespace Mediterranean College Esports" : "GSMC"
}

def _catch_names(name):
    alias = _KNOWN_NAMES.get(name)
    if alias is None:
        logging.warning(f"Unknown team name: {name}")
        return "une équipe"
    return alias

def get_competitions():
    yesterday = datetime.now(timezone.utc) - timedelta(days=2)
    week_plus_one = datetime.now(timezone.utc) + timedelta(days=7)

    leagues = ["First Stand", "MSI", "Worlds", "EM ", "EMEA Masters", "LEC", "LFL", "LCK", "LPL", "LTA", "LCP"]
    league_filter = "(" + " OR T.name LIKE ".join([f"'%{l}%'" for l in leagues]) + ")"

    site = EsportsClient("lol")
    response = site.cargo_client.query(
        tables="Tournaments=T, Leagues=L",
        join_on="T.League=L.League",
        fields="T.DateStart=Start, T.Date=End, T.Name, L.League_Short, T.Split, T.Year",
        where=f"T.DateStart <= '{week_plus_one}' AND ({league_filter}) AND (T.Date >= '{yesterday}' OR T.Date IS NULL)",
        group_by="T.Name"
    )

    # As LCK CL matches are not streamed on OTP, we decide do not include them in our dataset.
    data = [comp for comp in response if "LCK CL" not in comp["Name"]] #LCK academies
    data = [comp for comp in data if "LCK AS" not in comp["Name"]]
    data = [comp for comp in data if "Unicef" not in comp["Name"]] # ?
    data = [comp for comp in data if "LPLOL" not in comp["Name"]] #Ligue portugaise
    data = [comp for comp in data if "UEM" not in comp["Name"]] #Ligue amateur espagnole
    data = [comp for comp in data if "Road to LEC Finals" not in comp["Name"]]
    data = [comp for comp in data if "LEC Fan Clash" not in comp["Name"]]
    data = [comp for comp in data if "OPQ" not in comp["Name"]]
    return data

def get_schedule(competition: str):
    site = EsportsClient("lol")
    competition_data = site.cargo_client.query(
        tables="MatchSchedule=MS, Tournaments=T, Teamnames=Teams1, Teamnames=Teams2",
        join_on="MS.OverviewPage=T.OverviewPage, MS.Team1Final=Teams1.LongName, MS.Team2Final=Teams2.LongName",
        fields="MS.DateTime_UTC=Date, MS.Team1Final, MS.Team2Final, Teams1.Short=Short1, Teams2.Short=Short2, MS.BestOf, T.Name, MS.Winner, MS.Team1Score, MS.Team2Score, MS.MatchId, MS.Tab",
        where=f"T.Name = '{competition}'",
        group_by="Teams1.Short, Teams2.Short, MS.DateTime_UTC",
        order_by="MS.DateTime_UTC"
    )

    now = datetime.now(timezone.utc)

    to_remove = []

    for r in competition_data:
        if r["Date"] is None:
            to_remove.append(r)
            continue
        if r["Winner"] is None:
            scheduled_datetime = datetime.strptime(r["Date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            r["Status"] = "Ongoing" if scheduled_datetime < now else "Waiting"
        else:
            r["Status"] = "Done"

        if r["Short1"] is None:
            r["Short1"] = _catch_names(r["Team1Final"])
        _update_team_logo_url_from_api(r["Team1Final"], r["Short1"])

        if r["Short2"] is None:
            r["Short2"] = _catch_names(r["Team2Final"])
        _update_team_logo_url_from_api(r["Team2Final"], r["Short2"])

    for r in to_remove:
        competition_data.remove(r)

    return competition_data

@functools.lru_cache(maxsize=256)
def get_team_logo_url(shortcode: str) -> str:
    return _get_team_logo_urls().get(shortcode)

@functools.lru_cache(maxsize=1)
def _get_team_logo_urls() -> dict[str, str]:
    with open("logos.json", "r", encoding="utf-8") as f:
        return json.load(f)

def _update_team_logo_url_from_api(team: str, shortcode: str, refresh=False):
    # If refresh is not explicitly requested and the logo already exists, do nothing.

    if not refresh and get_team_logo_url(shortcode) is not None:
        return

    site = EsportsClient("lol")
    response = site.client.api(
        action="query",
        format="json",
        titles=f"File:{team}logo square.png",
        prop="imageinfo",
        iiprop="url",
        iiurlwidth=None,
    )

    # Black magic, see [docs example](https://lol.fandom.com/wiki/Help:Leaguepedia_API#Example_5.2:_Save_Team_image)
    image_info = next(iter(response["query"]["pages"].values())).get("imageinfo", [{}])[0]
    url = image_info.get('url')

    if url is None:
        logging.warning(f"No logo found for team {team}")
        return
    logging.info(f"URL updated for {team} ({shortcode}).")
    _upsert_team_logo(shortcode, url)

def _upsert_team_logo(shortcode: str, url: str):
    # To ensure correctness we reset the cache of the following functions.
    _get_team_logo_urls.cache_clear()
    get_team_logo_url.cache_clear()

    with open("logos.json", "r+", encoding="utf-8") as f:
        data = json.load(f)
        data[shortcode] = url
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()

def verbose_schedule(row, team):
    opponent = row["team1"] if team == row["team2"] else row["team2"]

    tournament = row["tournament"]
    LEC = ("LEC" in tournament)
    LFL = ("LFL" in tournament and not "Division 2" in tournament)
    Div2 = ("LFL" in tournament and "Division 2" in tournament)
    LCK = ("LCK" in tournament and not "CL" in tournament and not " AS " in tournament)
    LPL = ("LPL" in tournament and not " 2nd" in tournament)
    Worlds = (tournament.startswith("Worlds"))
    MSI = ("MSI" in tournament)
    EMEAM = (tournament.startswith("EM "))
    EWC = ("Esports World Cup" in tournament)

    if LEC:
        compet = "de LEC"
    if LPL:
        compet = "de LPL"
    if LFL:
        compet = "de LFL"
    if Div2:
        compet = "de Div2"
        if "Promotion" in tournament:
            compet = "de promotion en Div2"
    if LCK:
        compet = "de LCK"
    if Worlds:
        compet = "des Worlds"
    if MSI:
        compet = "du MSI"
    if EMEAM:
        compet = "des EMEA Masters"
    if EWC:
        compet = "de l'EWC"

    PI = "Play-In" in tournament
    if "MSI" in tournament:
        PI = "Play-In" in row["tab"]

    date = row["date"]
    if date.tzinfo is None:
        date = date.replace(tzinfo=ZoneInfo("UTC"))
    date = date.astimezone(ZoneInfo("Europe/Paris"))

    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

    if PI:
        intro = f"Pour le Play-In"
    elif "Day" in row["tab"]:
        intro = f"Pour le jour {row["tab"][4:]}"
    elif "Round" in row["tab"]:
        intro = f"Pour le {row["tab"]} des playoffs"
        if "Worlds" in compet:
            intro = f"Pour le Swiss stage"
    elif "Finals" in row["tab"]:
        intro = f"Pour la finale des playoffs"
    elif "Semifinals" in row["tab"]:
        intro = f"Pour la demi-finale des playoffs"
    elif "Quarterfinals" in row["tab"]:
        intro = f"Pour les quarts de finale des playoffs"
        if EWC:
            intro = f"Pour les quarts de finale"
    else:
        intro = f"Pour la semaine {row["tab"][5:]}"

    text = f"{intro} {compet}, {team}  jouera le {days[date.weekday()]} {date.strftime('%d')}/{date.strftime('%m')} vers {date.hour}h{date.minute if int(date.minute) > 0 else ''} contre {opponent} (BO{row["bo"]})."

    return text

def verbose_schedule_lfl(rows, team):
    opponents = [row["team1"] if team == row["team2"] else row["team2"] for row in rows]

    tournament = rows[0]["tournament"]

    compet = "de LFL"

    PI = "Play-In" in tournament

    for row in rows:
        date = row["date"]
        if date.tzinfo is None:
            date = date.replace(tzinfo=ZoneInfo("UTC"))
        row["date"] = date.astimezone(ZoneInfo("Europe/Paris"))

    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

    row = rows[0]
    if PI:
        intro = f"Pour le Play-In"
    elif "Day" in row["tab"]:
        intro = f"Pour le jour {row["tab"][4:]}"
    elif "Round" in row["tab"]:
        intro = f"Pour le {row["tab"]} des playoffs"
    elif "Finals" in row["tab"]:
        intro = f"Pour la finale des playoffs"
    elif "Semifinals" in row["tab"]:
        intro = f"Pour la demi-finale des playoffs"
    elif "Quarterfinals" in row["tab"]:
        intro = f"Pour les quarts de finale des playoffs"
    else:
        intro = f"Pour la semaine {row["tab"][5:]}"

    text = f"{intro} {compet}, {team}  jouera " + "et ".join([f"le {days[rows[i]["date"].weekday()]} {rows[i]["date"].strftime('%d')}/{rows[i]["date"].strftime('%m')} vers {rows[i]["date"].strftime('%Hh%M').replace('h00', 'h')} contre {opponents[i]} (BO{rows[i]["bo"]})" for i in range(len(rows))])

    return text
