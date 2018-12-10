import requests
import re
import pprint
import operator
import json
from operator import itemgetter

from urllib.request import urlopen
from bs4 import BeautifulSoup

# postgres imports
import os
from urllib import parse
import psycopg2

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
    p = re.compile("([A-z \-']+) - ([A-z\-']+) (['A-z \-']+)")

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

    # classes for different cell types
    player_class = 'playerHeading+border'
    header_class = 'heading+lborder+bborder'
    stat_class = 'lborder+bborder'

    index = 0
    column_builder = []
    column_headers = []
    shift_hash = {}
    team_shifts = []

    # Match "37 Cable, Jonathan", need to include slashes, periods and spaces in names as well
    p = re.compile("^([0-9]+) ([A-z\-\. ']+), ([A-z\-\. ']+)$")

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

                # we can't locate this player right now
                if player_id == 0:
                    continue

                # get shift start/end minute:second, and split them
                start_min, start_sec = player_hash['Start of ShiftElapsed / Game'][:5].split(':')
                end_min, end_sec = player_hash['End of ShiftElapsed / Game'][:5].split(':')

                # get the period, so we can differentiate the shift times
                period = player_hash['Per']

                shift = {}
                # if period is overtime, convert to '4'
                if (period == 'OT'):
                    period = 4;

                # convert each shift into a seconds timestamp
                shift['start'] = (int(start_min) * 60) + int(start_sec) + ((int(period) - 1) * 20 * 60)
                shift['end'] = (int(end_min) * 60) + int(end_sec) + ((int(period) - 1) * 20 * 60)
                shift['player_id'] = player_id
                # shift_hash[player_id].append(shift)

                # Add shift to list of team shifts
                team_shifts.append(shift)

            else:
                print("Error: No match for player={}".format(player))

    # sort by start of shift time
    team_shifts = sorted(team_shifts, key=itemgetter('start'), reverse=True)

    return team_shifts


def calculate_toi_deployments(shifts):

    # set current time on ice to zero
    current_toi = 0
    current_shifts = []
    icetime = {}

    while(len(shifts) > 0):
        shift = shifts.pop()

        # keep current shifts sorted by their expiration time
        current_shifts = sorted(current_shifts, key=itemgetter('end'))

        # check to see if we have ending shifts
        if len(current_shifts) > 0 and current_shifts[0]['end'] <= shift['start']:

            # calculate shift length
            shift_length = current_shifts[0]['end'] - current_toi
            current_toi = current_shifts[0]['end']

            line = set()
            # use a copy of current_shifts ([:]) so that we can modify it mid-loop
            for current_shift in current_shifts[:]:
                # set up the current line
                line.add(current_shift['player_id'])

                # remove all ending shifts
                if (current_shift['end'] <= shift['start']):
                    current_shifts.remove(current_shift)

            frozen_line = frozenset(line)

            if frozen_line in icetime:
                icetime[frozen_line] += shift_length
            else:
                icetime[frozen_line] = shift_length

        current_shifts.append(shift)

    return icetime


def calculate_lines(toi_deployments, players):

    forward_lines = {}
    defense_lines = {}

    for deployment, toi in toi_deployments.items():

        forwards = set()
        defense = set()
        for player_id in deployment:
            # name = players[player_id]['name']
            position = players[player_id]['position']
            if position == 'G':
                # goalie, we don't care
                continue
            elif position == 'D':
                # defense, find partner
                defense.add(player_id)
            else:
                # forward, find linemates
                forwards.add(player_id)

        if len(defense) == 2:
            frozen_defense = frozenset(defense)
            if frozen_defense in defense_lines:
                defense_lines[frozen_defense] += toi
            else:
                defense_lines[frozen_defense] = toi

        if len(forwards) == 3:
            frozen_forwards = frozenset(forwards)
            if frozen_forwards in forward_lines:
                forward_lines[frozen_forwards] += toi
            else:
                forward_lines[frozen_forwards] = toi

    sorted_forward_lines = sorted(forward_lines.items(), key=lambda kv: kv[1], reverse=True)

    pprint.pprint(sorted_forward_lines)

    lines_info = []
    depth = 1
    for forward_line, toi in sorted_forward_lines[:4]:
        for player_id in forward_line:
            info = {'player_id': player_id, 'depth': depth, 'toi': toi, 'position': players[player_id]['position'], 'state':'EVEN'}
            lines_info.append(info)
            print("{},".format(players[player_id]['name']), end =" ")
        depth += 1
        print("")

    sorted_defense_lines = sorted(defense_lines.items(), key=lambda kv: kv[1], reverse=True)

    pprint.pprint(sorted_defense_lines)

    depth = 1
    for defense_line, toi in sorted_defense_lines[:3]:
        for player_id in defense_line:
            info = {'player_id': player_id, 'depth': depth, 'toi': toi, 'position': players[player_id]['position'], 'state':'EVEN'}
            lines_info.append(info)
            print("{},".format(players[player_id]['name']), end =" ")
        depth += 1
        print("")

    return lines_info


def write_lines_to_database(game_id, team_id, line_info):
    # set up postgres connection
    parse.uses_netloc.append("postgres")
    url = parse.urlparse(os.environ["DATABASE_URL"])

    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )

    cur = conn.cursor()

    # CREATE TABLE lines (
    #     game_id integer,
    #     player_id integer,
    #     team_id integer NOT NULL,
    #     position character varying(5) NOT NULL,
    #     depth integer,
    #     state character varying(5),
    #     time_on_ice integer NOT NULL,
    #     CONSTRAINT lines_pkey PRIMARY KEY (game_id, player_id, depth, state)
    # );

    # Add game_id=%s when we expand to display multiple lines for different games
    delete_sql = """DELETE FROM lines WHERE team_id=%s"""

    # execute the DELETE statement
    cur.execute(delete_sql, [team_id])

    # get the number of deleted rows
    rows_deleted = cur.rowcount

    print("DELETED {} rows from the lines table for team_id={}".format(rows_deleted, team_id))

    sql = """INSERT INTO lines(game_id, player_id, team_id, position, depth, state, time_on_ice)
             VALUES(%s, %s, %s, %s, %s, %s, %s);"""

    for line in line_info:
        depth = line['depth']
        toi = line['toi']
        position = line['position']
        player_id = line['player_id']
        state = line['state']

        print("INSERTING game_id={} team_id={} player_id={} depth={} toi={} position={} state={}".format(game_id, team_id, player_id, depth, toi, position, state))

        # execute the INSERT statement
        cur.execute(sql, (game_id, player_id, team_id, position, depth, state, toi))

    # close communication with the PostgreSQL database server
    cur.close()
    # commit the changes
    conn.commit()

# get the games for today
todays_games = get_todays_games()

games = 1

# for each game, get the players and their shifts
for game_id, teams in todays_games.items():

    # limit to one game for testing
    if games > 10:
        break

    print(game_id)
    playbyplay_url = get_html_playbyplay_url(game_id)
    home_id = teams['home']
    away_id = teams['away']

    home_players = get_team_players(home_id)
    away_players = get_team_players(away_id)

    home_toi_url = get_home_html_timeonice_url(game_id)
    home_shifts = parse_time_on_ice(home_toi_url, home_players)
    home_toi_deploy = calculate_toi_deployments(home_shifts)
    home_line_info = calculate_lines(home_toi_deploy, home_players)

    # write the home lines to the LINES table in Postgresql
    write_lines_to_database(game_id, home_id, home_line_info)

    away_toi_url = get_away_html_timeonice_url(game_id)
    away_shifts = parse_time_on_ice(away_toi_url, away_players)
    away_toi_deploy = calculate_toi_deployments(away_shifts)
    away_line_info = calculate_lines(away_toi_deploy, away_players)

    # write the away lines to the LINES table in Postgresql
    write_lines_to_database(game_id, away_id, away_line_info)

    games += 1
    