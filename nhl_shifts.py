import requests
import re
import pprint
import operator
import json

from urllib.request import urlopen
from bs4 import BeautifulSoup

# the year range (2017-2018)
#First year that NHL.com released HTML Reports: 2003-2004
year = str(20182019)
game_id = str(20246)

# The url we will be scraping
# V stands for VISITOR and H stands for HOME
# 02 stands for REGULAR SEASON
# 01 stands for PRESEASON
# 0265 is the game id and it increments
def get_html_playbyplay_url(game_id):

    # get start/end year for season
    start_year = str(game_id)[0:4]
    end_year = str(int(start_year) + 1)

    # get the specific game number
    game_number = str(game_id)[4:]

    # generate url based on season and game number
    url = "http://www.nhl.com/scores/htmlreports/{}{}/PL{}.HTM".format(start_year,end_year,game_number)
    print('playbyplay url: ' + url)
    return url

def get_home_html_timeonice_url(year, game_id):
    url = "http://www.nhl.com/scores/htmlreports/" + year + "/TH0" + game_id + ".HTM"
    print('home url: ' + url)
    return url

def get_away_html_timeonice_url(year, game_id):
    url = "http://www.nhl.com/scores/htmlreports/" + year + "/TV0" + game_id + ".HTM"
    print('away url: ' + url)
    return url

def get_todays_schedule_url():
    url = "https://statsapi.web.nhl.com/api/v1/schedule"
    return url

def get_todays_games():
    url = get_todays_schedule_url()

    # get the html
    html = urlopen(url)
    data = json.load(html)

    todays_games = []

    for date in data['dates']:
        for game in date['games']:
            game_id = game['gamePk']
            home_team = game['teams']['home']['team']['name']
            away_team = game['teams']['home']['team']['name']

            todays_games.append(game_id)

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




# get the games for today
todays_games = get_todays_games()

for game_id in todays_games:
    print(game_id)
    playbyplay_url = get_html_playbyplay_url(game_id)

