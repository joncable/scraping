import requests
import re
import pprint
import operator

from urllib.request import urlopen
from bs4 import BeautifulSoup

# the year range (2017-2018)
#First year that NHL.com released HTML Reports: 2003-2004
year = str(20172018)
game_id = str(20001)

# The url we will be scraping
# V stands for VISITOR and H stands for HOME
# 02 stands for REGULAR SEASON
# 01 stands for PRESEASON
# 0265 is the game id and it increments
def get_html_playbyplay_url(year, game_id):
    url = "http://www.nhl.com/scores/htmlreports/" + year + "/PL0" + game_id + ".HTM"
    return url

def get_home_html_timeonice_url(year, game_id):
    url = "http://www.nhl.com/scores/htmlreports/" + year + "/TH0" + game_id + ".HTM"
    print('home url: ' + url)
    return url

def get_away_html_timeonice_url(year, game_id):
    url = "http://www.nhl.com/scores/htmlreports/" + year + "/TV0" + game_id + ".HTM"
    print('away url: ' + url)
    return url

def parse_time_on_ice(url):

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
            # get shift start/end minute:second, and split them
            start_min, start_sec = player_hash['Start of ShiftElapsed / Game'][:5].split(':')
            end_min, end_sec = player_hash['End of ShiftElapsed / Game'][:5].split(':')
     
            # get the period, so we can differentiate the shift times
            period = player_hash['Per']

            shift = {}
            # convert each shift into a seconds timestamp
            shift['start'] = (int(start_min) * 60) + int(start_sec) + ((int(period)-1) * 20 * 60)
            shift['end'] = (int(end_min) * 60) + int(end_sec) + ((int(period)-1) * 20 * 60)
            shift_hash[player].append(shift)

    # pretty print the list of player shifts, minute:seconds turned to seconds
    pprint.pprint(shift_hash)

    toi_together = {}
    player_toi = {}

    for player in shift_hash:
        print(player)
        toi_together[player] = {}
        for linemate in shift_hash:
            # don't compare shifts against himself, track their icetime separately
            if (linemate == player):
                player_toi[player] = 0
                for player_shift in shift_hash[player]:
                    player_toi[player] += player_shift['end'] - player_shift['start']
                continue
            toi_together[player][linemate] = 0      
            print('--> ' + linemate)
            for player_shift in shift_hash[player]:
                for linemate_shift in shift_hash[linemate]:
                    start = max(player_shift['start'], linemate_shift['start'])
                    end = min(player_shift['end'], linemate_shift['end'])
                    overlap = end - start
                    if (overlap > 0):
                        print('overlap=' + str(overlap))
                        toi_together[player][linemate] += overlap

    pprint.pprint(toi_together)

    sorted_players = {}

    for player in toi_together:
        player_dict = toi_together[player]
        sorted_player = sorted(player_dict.items(), key=operator.itemgetter(1), reverse=True)
        sorted_players[player] = sorted_player

    # sort player ice times as well
    sorted_player_toi = sorted(player_toi.items(), key=operator.itemgetter(1), reverse=True)

    return sorted_players, sorted_player_toi


def parse_playbyplay(url):
    # get the html
    html = urlopen(url)

    # create the BeautifulSoup object
    soup = BeautifulSoup(html, "lxml")

    # Possible spaces in between last names like JAMES VAN RIEMSDYK
    p = re.compile('([A-z ]+) - ([A-z]+) ([A-z ]+)')

    position_hash = {}

    for row in soup.find_all("tr"): 
        for cell in row.find_all("td"):
            for font in cell.find_all("font"):
                print('#######' + font['title'])
                matches = p.match(font['title'])
                if matches:
                    number = str(cell.text).strip()
                    position = matches.group(1)
                    first_name = matches.group(2)
                    last_name = matches.group(3)
                    position_hash[number + ' ' + last_name + ', ' + first_name] = position

    return position_hash


def compute_lines(sorted_players, position_hash, player_toi):
    team_lines = []
    for player_tuple in player_toi:
        player = player_tuple[0]

        # skip players that are already paired
        if (position_hash[player] == 'PAIRED'):
            continue

        line = []
        line.append(player)
        print('Finding linemates for: ' + player + ' (' + position_hash[player] + ')')
        forward_regex = re.compile('^[CLR]')
        defense_regex = re.compile('^[D]')
        goalie_regex = re.compile('^[G]')

        needed_linemates = 0
        if (forward_regex.match(position_hash[player])):
            needed_linemates = 2
            position_type = forward_regex
        elif (defense_regex.match(position_hash[player])):
            needed_linemates = 1
            position_type = defense_regex
        elif (goalie_regex.match(position_hash[player])):
            needed_linemates = 0
            position_type = goalie_regex

        linemate_array = []
        for potential_linemate in sorted_players[player]:
            if (needed_linemates > 0 and position_type.match(position_hash[potential_linemate[0]])):
                print('LINEMATE --> ' + potential_linemate[0])
                needed_linemates -= 1
                line.append(potential_linemate[0])
                position_hash[potential_linemate[0]] = 'PAIRED'

        position_hash[player] = 'PAIRED'
        team_lines.append(line)

    # sort lines by length (forwards, defense, goaltenders)
    team_lines.sort(key=len, reverse=True)    
    return team_lines



# build the url based on year and game id
home_url = get_home_html_timeonice_url(year, game_id)
sorted_home_players, home_player_toi = parse_time_on_ice(home_url)
print("################################# Home Player TOI #################################")
pprint.pprint(sorted_home_players)

away_url = get_away_html_timeonice_url(year, game_id)
sorted_away_players, away_player_toi = parse_time_on_ice(away_url)
print("################################# Home Player TOI #################################")
pprint.pprint(sorted_away_players)

playbyplay_url = get_html_playbyplay_url(year, game_id)
position_hash = parse_playbyplay(playbyplay_url)
print("################################# Position Hash #################################")
pprint.pprint(position_hash)

print("################################# Home Player TOI #################################")
pprint.pprint(home_player_toi)

print("################################# Computing Home Lines #################################")
home_team_lines = compute_lines(sorted_home_players, position_hash, home_player_toi)
print("################################# Home Lines #################################")
pprint.pprint(home_team_lines)

print("################################# Computing Away Lines #################################")
away_team_lines = compute_lines(sorted_away_players, position_hash, away_player_toi)
print("################################# Away Lines #################################")
pprint.pprint(away_team_lines)



