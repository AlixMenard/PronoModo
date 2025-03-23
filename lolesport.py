import requests
from datetime import datetime, timedelta, timezone
import json

# Base URL for Lolesport API
LOLESPORT_API_URL = "https://esports-api.lolesports.com/persisted/gw/getSchedule"


def get_competitions():
    now = datetime.now(timezone.utc)
    leagues = ["First Stand", "EMEA Masters", "LEC", "LFL", "LCK"]  # Example leagues to filter
    league_filter = "|".join([f"\"{l}\"" for l in leagues])

    # Call the Lolesport API to fetch the schedule
    params = {
        "startDate": now.strftime("%Y-%m-%d"),
        "endDate": (now + timedelta(30)).strftime("%Y-%m-%d"),
        "leagueFilter": league_filter
    }

    response = requests.get(LOLESPORT_API_URL, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from Lolesport API: {response.status_code}")

    data = response.json()
    competitions = [comp['tournament']['name'] for comp in data['data']['schedule']]

    return competitions


def get_schedule(competition: str):
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Call the Lolesport API to fetch the schedule for a specific competition
    params = {
        "startDate": now.strftime("%Y-%m-%d"),
        "endDate": (now + timedelta(7)).strftime("%Y-%m-%d"),
        "competition": competition
    }

    response = requests.get(LOLESPORT_API_URL, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from Lolesport API: {response.status_code}")

    data = response.json()
    schedule = data['data']['schedule']

    # Process schedule data to add match status
    now = datetime.now(timezone.utc)
    for match in schedule:
        match_date = datetime.strptime(match['startTime'], "%Y-%m-%dT%H:%M:%S.%fZ")
        if match.get("winner") is not None:
            match["Status"] = "Done"
        elif match_date < now:
            match["Status"] = "Ongoing"
        else:
            match["Status"] = "Waiting"

    return schedule


def get_filename_url_to_open(team, width=None):
    # Call the Lolesport API for the team logo
    url = f"https://api.lolesports.com/persisted/gw/getTeams"

    params = {
        "teamName": team
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from Lolesport API: {response.status_code}")

    data = response.json()
    team_data = data['data']['teams'][0]  # Assuming we get a single team

    logo_url = team_data['logoUrl']

    # If a width is specified, we can modify the logo URL to fetch the thumbnail
    if width:
        logo_url = logo_url.replace("original", f"thumb{width}")

    return logo_url

