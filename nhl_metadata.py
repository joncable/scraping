import requests
import re
import pprint
import operator
import json
from operator import itemgetter

from urllib.request import urlopen

# postgres imports
import os
from urllib import parse
import psycopg2


def get_nhl_teams_url():
    url = "https://statsapi.web.nhl.com/api/v1/teams"
    return url

def get_nhl_team_players_url(team_id):
    url = "https://statsapi.web.nhl.com/api/v1/teams/{}?expand=team.roster".format(team_id)
    return url

def get_records_nhl_team_players_url(team_id):
    url = "https://records.nhl.com/site/api/player/byTeam/{}".format(team_id)
    return url

def get_nhl_teams():
    teams_url = get_nhl_teams_url()

    # get the html
    html = urlopen(teams_url)
    data = json.load(html)

    teams_data = data['teams']
    return teams_data

def write_player_to_database(player_id, team_id, player_name, position, player_number):

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

    # Delete this player_id
    delete_sql = """DELETE FROM players WHERE player_id=%s"""

    # execute the DELETE statement
    cur.execute(delete_sql, [player_id])

    sql = """INSERT INTO players(player_id, team_id, name, position, number)
             VALUES(%s, %s, %s, %s, %s);"""

    # INSERT INTO the_table(id, column_1, column_2)
    # VALUES(1, 'A', 'X'), (2, 'B', 'Y'), (3, 'C', 'Z')
    # ON CONFLICT(id) DO UPDATE SET
    # column_1 = excluded.column_1,
    # column_2 = excluded.column_2;

    print("INSERTING player_id={} team_id={} name={} position={} number={}".format(
                     player_id, team_id, player_name, position, player_number))

    # execute the INSERT statement
    cur.execute(sql, (player_id, team_id, player_name, position, player_number))

    # close communication with the PostgreSQL database server
    cur.close()

    # commit the changes
    conn.commit()

    return

def write_team_to_database(team_id, name, location, venue, team_name, division, conference):

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

    # Delete this player_id
    delete_sql = """DELETE FROM teams WHERE team_id=%s"""

    # execute the DELETE statement
    cur.execute(delete_sql, [team_id])

    sql = """INSERT INTO teams(team_id, name, location, venue, team_name, division, conference)
             VALUES(%s, %s, %s, %s, %s, %s, %s);"""

    # INSERT INTO the_table(id, column_1, column_2)
    # VALUES(1, 'A', 'X'), (2, 'B', 'Y'), (3, 'C', 'Z')
    # ON CONFLICT(id) DO UPDATE SET
    # column_1 = excluded.column_1,
    # column_2 = excluded.column_2;

    print("INSERTING team_id={} name={} location={} venue={} team_name={} division={} conference={}".format(
                     team_id, name, location, venue, team_name, division, conference))

    # execute the INSERT statement
    cur.execute(sql, (team_id, name, location, venue, team_name, division, conference))

    # close communication with the PostgreSQL database server
    cur.close()

    # commit the changes
    conn.commit()

    return

def get_records_team_players(team_id):
    players_url = get_records_nhl_team_players_url(team_id)

    # get the html
    html = urlopen(players_url)
    data = json.load(html)

    roster = data['data']

    for player in roster:
        player_id = player['id']
        player_name = player['fullName']
        position = player['position']
        handedness = player['shootsCatches']

        # jersey numbers aren't always set, default to zero
        if 'sweaterNumber' in player:
            player_number = player['sweaterNumber']
        else:
            player_number = 0

        write_player_to_database(player_id, team_id, player_name, position, player_number)

def get_team_players(team_id):
    players_url = get_nhl_team_players_url(team_id)

    # get the html
    html = urlopen(players_url)
    data = json.load(html)

    roster = data['teams'][0]['roster']['roster']

    for player in roster:
        player_id = player['person']['id']
        player_name = player['person']['fullName']
        position = player['position']['code']

        # jersey numbers aren't always set, default to zero
        if 'jerseyNumber' in player:
            player_number = player['jerseyNumber']
        else:
            player_number = 0

        write_player_to_database(player_id, team_id, player_name, position, player_number)

teams = get_nhl_teams()
for team in teams:
    team_id = team['id']
    name = team['name']
    venue = team['venue']['name']
    location = team['locationName']
    team_name = team['teamName']
    division = team['division']['id']
    conference = team['conference']['id']

    # write_team_to_database(team_id, name, location, venue, team_name, division, conference)

    players = get_records_team_players(team_id)


