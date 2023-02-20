"""Uses Riot's API to gather a player's data from their last 20 ranked games.

Accesses the Riot API using the `LolWatcher` class to find a specific player
using their `puuid` and their 20 most recent matches using `matchId`s. This
information is then parsed, filtered, renamed, and reorganized as necessary to
create easy-to-read data, which is then dumped into a 

Typical usage example:
    python collect_ranked_stats.py NA1 Zenîth
"""

import sys
import time

import pandas as pd
import lol_id_tools as lit
from riotwatcher import LolWatcher, ApiError

# Create a file called `constants.py` and place your Riot API key in it. Ex:
# `RIOT_API_KEY = '<your api key here>'`
import constants


def main() -> None:
    """Collects and processes the required data, then writes it to a file."""
    check_user_input()

    lol_watcher = LolWatcher(constants.RIOT_API_KEY)
    region = get_region(sys.argv[1])
    summoner = get_summoner(lol_watcher, region, sys.argv[2])
    puuid = get_puuid(summoner)
    match_ids = get_last_20_match_ids(lol_watcher, region, puuid)

    data = collect_data(lol_watcher, region, match_ids, puuid)
    data = rename_shard_columns(data)
    data = filter_and_decode_data(data)
    data = sort_data(data)

    save_data_to_pickle(data, summoner)


def check_user_input() -> None:
    """Checks the user's input to make sure the format is correct."""
    if len(sys.argv) != 3:
        print('Incorrect number of arguments were provided.\n')
        print('Run the program again with the following arguments:')
        print('python collect_ranked_stats.py {region name} {summoner name}\n')
        print('Example: python collect_ranked_stats.py NA1 Zenîth')
        sys.exit(2)


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
        data = pd.concat([data, player_data], ignore_index=True)

    data = get_runes(data)
    return data


def rename_shard_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Renames the `statPerks` columns using an easy-to-read convention.
    
    Args:
        data: The `DataFrame` to update.

    Returns:
        The updated `DataFrame`.
    """
    new_names = {
        'perks.statPerks.defense': 'runeShardDefense',
        'perks.statPerks.flex': 'runeShardFlex',
        'perks.statPerks.offense': 'runeShardOffense',
    }
    data = data.rename(columns=new_names)
    return data


def filter_and_decode_data(data: pd.DataFrame) -> pd.DataFrame:
    """Remove unnecessary information from the data and translate id's to names.

    Args:
        data: The `DataFrame` to update.

    Returns:
        The updated `DataFrame`.
    """
    data = remove_unnecessary_info(data)
    data = decode_items(data)
    data = decode_summoner_spells(data)
    data = decode_runes(data)
    data = decode_shards(data)
    return data


def sort_data(data: pd.DataFrame) -> pd.DataFrame:
    """Sorts the given data by column name.
    
    Args:
        data: The `DataFrame` to update.

    Returns:
        The updated `DataFrame`.
    """
    data = data.sort_index(axis=1)
    return data

def save_data_to_pickle(data: pd.DataFrame, summoner: dict) -> None:
    """Saves `data` in a `pickle` file.
    
    Args:
        data: The `DataFrame` to save.
        summoner: The information of the given summoner.
    """
    name = summoner['name']
    time_str = time.strftime("%Y%m%d-%H%M%S")
    data.to_pickle(f'{name}_ranked_stats_{time_str}.pickle')


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
        data: The `DataFrame` containing the collected player data.
    
    Returns:
        The `DataFrame` with rune information appended to it.
    """
    perks = pd.json_normalize(data['perks.styles'])
    primary = pd.json_normalize(pd.json_normalize(perks[0])['selections'])
    keystone = pd.json_normalize(primary[0])['perk']
    primary1 = pd.json_normalize(primary[1])['perk']
    primary2 = pd.json_normalize(primary[2])['perk']
    primary3 = pd.json_normalize(primary[3])['perk']
    secondary = pd.json_normalize(pd.json_normalize(perks[1])['selections'])
    secondary1 = pd.json_normalize(secondary[0])['perk']
    secondary2 = pd.json_normalize(secondary[1])['perk']

    keystone.name = 'runeKeystone'
    primary1.name = 'runePrimary1'
    primary2.name = 'runePrimary2'
    primary3.name = 'runePrimary3'
    secondary1.name = 'runeSecondary1'
    secondary2.name = 'runeSecondary2'
    rune_list = [keystone, primary1, primary2, primary3, secondary1, secondary2]
    runes = pd.concat(rune_list, axis=1)
    data = pd.concat([data, runes], axis=1, join='outer')
    return data


def remove_unnecessary_info(data: pd.DataFrame) -> pd.DataFrame:
    """Remove unnecessary fields from the acquired data.

    Args:
        data: The `DataFrame` containing the collected player data.

    Returns:
        The data with unnecessary information removed.    
    """
    data = data.drop(columns=[
        'perks.styles', 'unrealKills', 'totalUnitsHealed', 'summonerId',
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
    data = data.drop(list(data.filter(regex=regex)), axis=1)
    return data


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


def decode_runes(data: pd.DataFrame) -> pd.DataFrame:
    """Translates the id's of every rune to its name.

    Args:
        data: The `DataFrame` of player stats.

    Returns:
        The updated `DataFrame`.
    """
    runes = data.filter(regex=r'rune((Keystone)|(Primary)|(Secondary))')
    data[runes.columns] = data[runes.columns].applymap(
        lambda rune: lit.get_name(rune, object_type='rune')
    )
    return data


def decode_shards(data: pd.DataFrame) -> pd.DataFrame:
    """Translates the id's of every rune shard to its name.

    Args:
        data: The `DataFrame` of player stats.

    Returns:
        The updated `DataFrame`.
    """
    translations = {
        5001: 'Health', 5002: 'Armor', 5003: 'Magic Resist',
        5005: 'Attack Speed', 5007: 'Ability Haste', 5008: 'Adaptive Force'
    }
    shards = data.filter(regex=r'runeShard*')
    data[shards.columns] = data[shards.columns].applymap(
        lambda shard: translations.get(shard)
    )
    return data


if __name__ == '__main__':
    main()
