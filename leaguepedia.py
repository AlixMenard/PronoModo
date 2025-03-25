from mwrogue.esports_client import EsportsClient
from datetime import datetime, timedelta, timezone
import json
import urllib.request

def get_competitions():
    now = datetime.now(timezone.utc) #- timedelta(30) .strftime("%Y-%m-%d")
    site = EsportsClient("lol")
    leagues = ["First Stand", "MSI", "Worlds", "EM ", "EMEA Masters", "LEC", "LFL", "LCK"] #off LCK CL
    league_filter = "(" + " OR T.name LIKE ".join([f"'%{l}%'" for l in leagues]) + ")" #(T.Name LIKE '%LEC%' OR T.Name LIKE '%LCK%' OR T.Name LIKE '%LFL%' OR T.Name LIKE '%LPL%')
    response = site.cargo_client.query(
        tables = "MatchSchedule=MS, Tournaments=T",
        join_on="MS.OverviewPage=T.OverviewPage",
        fields="T.DateStart=Start, T.Date=End, T.Name",
        where=f"T.Date >= '{now-timedelta(1)}' AND {league_filter}", #
        group_by="T.Name"
    )
    json_data = json.dumps(response, indent=2)
    json_data = json.loads(json_data)
    json_data = [comp for comp in json_data if "LCK CL" not in comp["Name"]]
    return json_data

def get_schedule(competition:str):
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    site = EsportsClient("lol")
    response = site.cargo_client.query(
        tables="MatchSchedule=MS, Tournaments=T, Teamnames=Teams1, Teamnames=Teams2",
        join_on="MS.OverviewPage=T.OverviewPage, MS.Team1Final=Teams1.LongName, MS.Team2Final=Teams2.LongName",
        fields="MS.DateTime_UTC=Date, MS.Team1Final, MS.Team2Final, Teams1.Short=Short1, Teams2.Short=Short2, MS.BestOf, T.Name, MS.Winner, MS.Team1Score, MS.Team2Score",
        where=f"T.Name = '{competition}'",
        group_by="Teams1.Short, Teams2.Short"
    )
    json_data = json.dumps(response, indent=2)
    json_data = json.loads(json_data)
    now = datetime.now(timezone.utc)
    for r in json_data:
        r["Status"] = "Done" if r["Winner"] is not None else "Ongoing" if datetime.strptime(r["Date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)<now else "Waiting"
 
     with open("logos.json", "r", encoding="utf-8") as f:
         data = json.load(f)
     for r in json_data:
         t1, t2 = r["Team1Final"], r["Team2Final"]
         t1s, t2s = r["Short1"], r["Short2"]
         if not t1s in data:
             data[t1s] = get_team_logo_url(t1)
         if not t2s in data:
             data[t2s] = get_team_logo_url(t2)
 
     with open("logos.json", "w", encoding="utf-8") as f:
         json.dump(data, f, indent=2)
 
    return json_data


def get_team_logo_url(team: str, width=None):
    site = EsportsClient("lol")
    filename = f"{team}logo square.png"
    response = site.client.api(
        action="query",
        format="json",
        titles=f"File:{filename}",
        prop="imageinfo",
        iiprop="url",
        iiurlwidth=width,
    )

    image_info = next(iter(response["query"]["pages"].values())).get("imageinfo", [{}])[0]

    if not image_info:
        return None  # Return None if no image info is found

    return image_info["thumburl"] if width else image_info["url"]
