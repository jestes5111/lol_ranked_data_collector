"""temp"""

import sys
import json
import pandas as pd
import lol_id_tools as lit
from riotwatcher import LolWatcher, ApiError

# Create a file called `constants.py` and place your Riot API key in it. Ex:
# `RIOT_API_KEY = '<your api key here>'`
import constants


def main():
    """temp"""
    lol_watcher = LolWatcher(constants.RIOT_API_KEY)
    region = get_region('NA1')
    summoner = get_summoner(lol_watcher, region, 'Zenîth')
    puuid = summoner['puuid']
    match_ids = get_last_20_match_ids(lol_watcher, region, puuid)

    data = collect_data(lol_watcher, region, match_ids, puuid)
    data = filter_and_decode_data(data)

    data.to_csv('test.csv', index=False)

    # TODO: expand 'perks' column to shards (offense, flex, defense) and
    #       runes (listed as 'primaryStyle' and 'subStyle' with 'selections')


def get_region(region: str) -> str:
    """Checks the user's region and returns it if it's valid.

    Args:
        region: The user's desired region name as a string.

    Returns:
        The user's region as a string.
    """

    valid_regions = {
        'BR1', 'EUN1', 'EUW1', 'JP1', 'KR', 'LA1', 'LA2', 'NA1',
        'OC1', 'PH2', 'RU', 'SG2', 'TH2', 'TR1', 'TW2', 'VN2'
    }
    if region.upper().strip() in valid_regions:
        return region

    print(f'"{region}" does not exist. Enter a valid region and try again.')
    print(f'Valid regions:  {", ".join(valid_regions)}')
    sys.exit(2)


def get_summoner(watcher: LolWatcher, region: str, summoner_name: str) -> dict:
    """Attemps to find the player. Returns the player if found, exits otherwise.

    Args:
        watcher: The `LolWatcher` object used to make HTTP requests.
        region: The user's desired region as a string.
        summoner_name: The user's desired summoner name as a string.

    Returns:
        The player's information represented as a dict. Note that in the Riot
        Developer  Portal, it is returned as a `SummonerDTO`, but is converted
        to a dict by `riotwatcher`.
    """
    try:
        summoner = watcher.summoner.by_name(region, summoner_name)
    except ApiError as error:
        if error.response.status_code == 404:
            print(f'Summoner "{summoner_name}" was not found. Try again.')
            sys.exit(2)
    return summoner


def get_puuid(summoner: dict) -> str:
    """Gets the puuid of `summoner`.

    Args:
        summoner: The information of the given summoner.

    Returns:
        The puuid string value.
    """
    return summoner['puuid']


def get_last_20_match_ids(
    watcher: LolWatcher,
    region: str,
    puuid: str
) -> list[str]:
    """Gets the `matchId` of the last 20 matches.

    Args:
        watcher: The `LolWatcher` object to access Riot's API.
        region: The region to search (e.g., 'NA1').
        puuid: The globally unique identifier of a given player.

    Returns:
        A list of 20 `matchId`s.
    """
    ranked = 420  # Riot's queueId value for Ranked Summoner's Rift
    return watcher.match.matchlist_by_puuid(region, puuid, queue=ranked)


def collect_data(
    watcher: LolWatcher,
    region: str,
    match_ids: list[str],
    puuid: str
) -> pd.DataFrame:
    """Gathers player data from their last 20 ranked matches.

    Args:
        watcher: The `LolWatcher` object to access Riot's API.
        region: The region to search (e.g., 'NA1').
        match_id: A list `matchId`s, used to get data from individual matches.
        puuid: The globally unique identifier of a given player.

    Returns:
        A `DataFrame` containing all of their unfiltered data.
    """
    data = pd.DataFrame()

    for match_id in match_ids:
        match = get_match_from_id(watcher, region, match_id)
        player_index = get_player_index(puuid, match)
        player = get_player_from_index(match, player_index)
        player_data = pd.json_normalize(player)
        #player_data = pd.DataFrame([player])
        data = pd.concat([data, player_data], ignore_index=True)
        #data = get_runes(data)

    return data


def filter_and_decode_data(data: pd.DataFrame) -> pd.DataFrame:
    """Remove unnecessary information from the data and translate id's to names.

    Args:
        data: The `DataFrame` to update.

    Returns:
        The updated `DataFrame`.
    """
    pd.json_normalize(data['perks.styles'])
    data = remove_unnecessary_info(data)
    data = decode_items(data)
    data = decode_summoner_spells(data)
    return data


def get_match_from_id(
    watcher: LolWatcher,
    region: str,
    match_id: str
) -> list[str]:
    """Gets the `matchDto` of the desired ranked match from its `matchId`.

    Args:
        watcher: The `LolWatcher` object to access Riot's API.
        region: The region to search (e.g., 'NA1').
        match_id: The `matchId` of the given match.

    Returns:
        A list of 20 `matchId`s.
    """
    return watcher.match.by_id(region, match_id)


def get_player_index(puuid: str, match: dict) -> int:
    """Gets the index of the desired player in a game.

    Args:
        puuid: The Player Universallly Unique IDentifier of a given player.
        match: The information related to a given match.

    Returns:
        The information related to `player` in the game defined as `match`.
    """
    return match['metadata']['participants'].index(puuid)


def get_player_from_index(match: dict, index: int) -> dict:
    """Gets a desired player from a match using their `participantId` (`index`).

    Args:
        match: The match being searched for data.
        index: The `participantId` of the player, an int value 0-9.

    Returns:
        The player's information from the given match as a `playerDto` (dict).
    """
    return match['info']['participants'][index]


def get_runes(data: pd.DataFrame) -> pd.DataFrame:
    """Gets the runes used by the player in an individual match.
    
    Args:
        data: 
    """
    perks = pd.json_normalize(data['perks.styles'])
    primary = pd.json_normalize(perks[0])['selections']
    # TODO: go from here

    secondary = pd.json_normalize(perks[1])['selections']


def remove_unnecessary_info(data: pd.DataFrame) -> pd.DataFrame:
    """Remove unnecessary fields from the acquired data.

    Args:
        data: The `DataFrame` containing the collected player data.

    Returns:
        The data with unnecessary information removed.    
    """
    data = data.drop(columns=[
        'unrealKills', 'totalUnitsHealed', 'summonerId',
        'summonerLevel', 'summonerName', 'role', 'puuid', 'profileIcon',
        'largestCriticalStrike', 'lane', 'itemsPurchased', 'individualPosition',
        'goldSpent', 'eligibleForProgression', 'championTransform', 'championId'
    ])

    regexes = ['.*challenge*', '.*Ping*', '.*riot*', '.*nexus*', '.*gameEnded*']
    for regex in regexes:
        filter_data(data, regex)

    return data


def filter_data(data: pd.DataFrame, regex: str) -> pd.DataFrame:
    """Remove a column from the given `DataFrame` using the given `regex`.

    Args:
        data: The `DataFrame` to remove one or more columns from.
        regex: The regular expression to search for.

    Returns:
        The given `DataFrame` with the desired column(s) removed.
    """
    return data.drop(list(data.filter(regex=regex)), axis=1, inplace=True)


def decode_items(data: pd.DataFrame) -> pd.DataFrame:
    """Translates the id's of every item to its name.

    Args:
        data: The `DataFrame` of player stats.

    Returns:
        The updated `DataFrame`.
    """
    items = data.filter(regex=r'item\d')
    data[items.columns] = data[items.columns].applymap(
        lambda item: lit.get_name(item, object_type='item')
    )
    return data


def decode_summoner_spells(data: pd.DataFrame) -> pd.DataFrame:
    """Translates the id's of every summoner spell to its name.

    Args:
        data: The `DataFrame` of player stats.

    Returns:
        The updated `DataFrame`.
    """
    summoner_spells = data.filter(regex=r'summoner([1-2])Id')
    data[summoner_spells.columns] = data[summoner_spells.columns].applymap(
        lambda spell: lit.get_name(spell, object_type='summoner_spell')
    )
    return data


if __name__ == '__main__':
    main()