import requests
import re
import pprint
import operator
import json

from urllib.request import urlopen
from bs4 import BeautifulSoup

def get_game_from_gameid(game_id):
    # get the specific game number
    game_number = str(game_id)[4:]

    return game_number

def get_season_from_gameid(game_id):

    # get start/end year for season
    start_year = str(game_id)[0:4]
    end_year = str(int(start_year) + 1)

    return "{}{}".format(start_year, end_year)

# The url we will be scraping
# V stands for VISITOR and H stands for HOME
# 02 stands for REGULAR SEASON
# 01 stands for PRESEASON
# 0265 is the game id and it increments
def get_html_playbyplay_url(game_id):

    # get start/end year for season and game number
    season = get_season_from_gameid(game_id)
    game_number = get_game_from_gameid(game_id)

    # generate url based on season and game number
    url = "http://www.nhl.com/scores/htmlreports/{}/PL{}.HTM".format(season, game_number)
    print('playbyplay url: ' + url)
    return url

def get_home_html_timeonice_url(game_id):

    # get start/end year for season and game number
    season = get_season_from_gameid(game_id)
    game_number = get_game_from_gameid(game_id)

    url = "http://www.nhl.com/scores/htmlreports/{}/TH{}.HTM".format(season, game_number)
    print('home url: ' + url)
    return url

def get_away_html_timeonice_url(game_id):

    # get start/end year for season and game number
    season = get_season_from_gameid(game_id)
    game_number = get_game_from_gameid(game_id)

    url = "http://www.nhl.com/scores/htmlreports/{}/TV{}.HTM".format(season, game_number)
    print('away url: ' + url)
    return url

def get_todays_schedule_url():
    url = "https://statsapi.web.nhl.com/api/v1/schedule"
    return url

def get_team_players_url(team_id):
    url = "https://statsapi.web.nhl.com/api/v1/teams/" + str(team_id) + "?expand=team.roster"
    print('team_players url: ' + url)
    return url

def get_team_players(team_id):
    team_players_url = get_team_players_url(team_id)

    # get the html
    html = urlopen(team_players_url)
    data = json.load(html)

    roster = data['teams'][0]['roster']['roster']

    team_players = {}

    for player in roster:
        player_id = player['person']['id']
        player_name = player['person']['fullName']
        position = player['position']['code']

        # jersey numbers aren't always set, default to zero
        if 'jerseyNumber' in player:
            player_number = player['jerseyNumber']
        else:
            player_number = 0

        print("id=" + str(player_id) + "name=" + player_name)

        team_players[player_id] = {'name': player_name,
                                   'number': player_number,
                                   'position': position}

    return team_players


def get_todays_games():
    url = get_todays_schedule_url()

    # get the html
    html = urlopen(url)
    data = json.load(html)

    todays_games = {}

    for date in data['dates']:
        for game in date['games']:
            game_id = game['gamePk']
            home_team = game['teams']['home']['team']['name']
            home_id = game['teams']['home']['team']['id']
            away_team = game['teams']['away']['team']['name']
            away_id = game['teams']['away']['team']['id']

            todays_games[game_id] = {'home': home_id,
                                     'away': away_id}


            print("{} - {} @ {}".format(game_id, away_team, home_team))

    return todays_games



def parse_playbyplay(url):
    # get the html
    html = urlopen(url)

    # create the BeautifulSoup object
    soup = BeautifulSoup(html, "lxml")

    # Possible spaces in between last names like JAMES VAN RIEMSDYK
    # Also allow for dashes in their name
    p = re.compile('([A-z \-]+) - ([A-z\-]+) ([A-z \-]+)')

    position_hash = {}

    for row in soup.find_all("tr"): 
        for cell in row.find_all("td"):
            for font in cell.find_all("font"):
                matches = p.match(font['title'])
                if matches:
                    number = str(cell.text).strip()
                    position = matches.group(1)
                    first_name = matches.group(2)
                    last_name = matches.group(3)
                    position_hash[number + ' ' + last_name + ', ' + first_name] = position

    return position_hash


def find_player_id(number, first_name, last_name, players):

    for player_id, details in players.items():
        if ("{} {}".format(first_name, last_name).lower() == details['name'].lower()):
            return player_id

    print("Error: Could not find player_id for {}, {}".format(last_name, first_name))
    return 0

def parse_time_on_ice(url, players):
    # get the html
    html = urlopen(url)

    # create the BeautifulSoup object
    soup = BeautifulSoup(html, "lxml")

    # regexes for grabbing players/columns
    player_regex = '^([0-9]+) ([A-z]+), ([A-z]+)$'
    column_regex = '[A-z]+'

    # classes for different cell types
    player_class = 'playerHeading+border'
    header_class = 'heading+lborder+bborder'
    stat_class = 'lborder+bborder'

    index = 0
    column_builder = []
    column_headers = []
    shift_hash = {}

    # Match "37 Cable, Jonathan", need to include slashes, periods and spaces in names as well
    p = re.compile('^([0-9]+) ([A-z\-\. ]+), ([A-z\-\. ]+)$')

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        player_hash = {}
        for cell in cells:
            c = cell.get('class')
            if c is None:
                continue
            elif ''.join(c) == player_class:
                player = cell.text
                shift_hash[player] = []
            elif ''.join(c) == header_class:
                column_builder.append(cell.text)
            elif ''.join(c) == stat_class:
                if len(column_builder) > 0:
                    column_headers = column_builder
                    column_builder = []

                player_hash[column_headers[index]] = cell.text
                index += 1
                index = (index % len(column_headers))

        if (player_hash):

            # map player information to player id
            matches = p.match(player)
            if matches:
                number = matches.group(1)
                last_name = matches.group(2)
                first_name = matches.group(3)
                player_id = find_player_id(number, first_name, last_name, players)

                # get shift start/end minute:second, and split them
                start_min, start_sec = player_hash['Start of ShiftElapsed / Game'][:5].split(':')
                end_min, end_sec = player_hash['End of ShiftElapsed / Game'][:5].split(':')

                # get the period, so we can differentiate the shift times
                period = player_hash['Per']

                shift = {}
                # convert each shift into a seconds timestamp
                shift['start'] = (int(start_min) * 60) + int(start_sec) + ((int(period) - 1) * 20 * 60)
                shift['end'] = (int(end_min) * 60) + int(end_sec) + ((int(period) - 1) * 20 * 60)
                shift_hash[player_id].append(shift)
            else:
                print("NO MATCH FOR player={}".format(player))

    # pretty print the list of player shifts, minute:seconds turned to seconds
    # pprint.pprint(shift_hash)

# get the games for today
todays_games = get_todays_games()

# for each game, get the players and their shifts
for game_id, teams in todays_games.items():
    print(game_id)
    playbyplay_url = get_html_playbyplay_url(game_id)
    home_id = teams['home']
    away_id = teams['away']

    home_players = get_team_players(home_id)
    away_players = get_team_players(away_id)

    home_toi_url = get_home_html_timeonice_url(game_id)
    parse_time_on_ice(home_toi_url, home_players)





