from mwrogue.esports_client import EsportsClient
from datetime import datetime, timedelta, timezone
import json
import urllib.request

"""
site = EsportsClient("lol")
    response = site.cargo_client.query(
        tables="MatchSchedule=MS, Tournaments=T, Teamnames=Teams1, Teamnames=Teams2",
        join_on="MS.OverviewPage=T.OverviewPage, Teams1.LongName=MS.Team1, Teams2.LongName=MS.Team2",
        fields="MS.DateTime_UTC=Date, T.Name, MS.Team1, MS.Team2, Teams1.Short=Short1, Teams2.Short=Short2, MS.BestOf, MS.Tab",
        where=f"MS.DateTime_UTC > '2025-02-04' AND MS.DateTime_UTC <= '2025-02-06'",
        order_by="DateTime_UTC"
    )

    # Convert the OrderedDict to a JSON-formatted string
    json_data = json.dumps(response, indent=2)
    json_data = json.loads(json_data)
    competitions = set()
    for match in json_data:
        print(match)
"""


def get_competitions():
    now = datetime.now(timezone.utc) #- timedelta(30) .strftime("%Y-%m-%d")
    site = EsportsClient("lol")
    leagues = ["First Stand", "EM ", "EMEA Masters", "LEC", "LFL", "LCK"] #off LCK CL
    league_filter = "(" + " OR T.name LIKE ".join([f"'%{l}%'" for l in leagues]) + ")" #(T.Name LIKE '%LEC%' OR T.Name LIKE '%LCK%' OR T.Name LIKE '%LFL%' OR T.Name LIKE '%LPL%')
    response = site.cargo_client.query(
        tables = "MatchSchedule=MS, Tournaments=T",
        join_on="MS.OverviewPage=T.OverviewPage",
        fields="T.DateStart=Start, T.Date=End, T.Name",
        where=f"T.Date >= '{now-timedelta(1)}' AND T.DateStart <= '{now}' AND {league_filter}", #
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
        fields="MS.DateTime_UTC=Date, MS.Team1, MS.Team2, Teams1.Short=Short1, Teams2.Short=Short2, MS.BestOf, T.Name, MS.Winner, MS.Team1Score, MS.Team2Score",
        where=f"T.Date >= '{now}' AND T.DateStart <= '{now + timedelta(7)}' AND T.Name = '{competition}' AND MS.Team1 != 'TBD' AND MS.Team2 != 'TBD'",
        group_by="Teams1.Short, Teams2.Short"
    )
    json_data = json.dumps(response, indent=2)
    json_data = json.loads(json_data)
    now = datetime.now(timezone.utc)
    for r in json_data:
        r["Status"] = "Done" if r["Winner"] is not None else "Ongoing" if datetime.strptime(r["Date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)<now else "Waiting"
    return json_data


def get_filename_url_to_open(team, width=None):
    filename = f"{team}logo square.png"
    site = EsportsClient("lol")
    response = site.client.api(
        action="query",
        format="json",
        titles=f"File:{filename}",
        prop="imageinfo",
        iiprop="url",
        iiurlwidth=width,
    )

    image_info = next(iter(response["query"]["pages"].values()))["imageinfo"][0]

    if width:
        url = image_info["thumburl"]
    else:
        url = image_info["url"]

    #In case you would like to save the image in a specific location, you can add the path after 'url,' in the line below.
    urllib.request.urlretrieve(url, "logos\\" + team + '.png')