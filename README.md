# lol_ranked_data_collector
Collects player data from ranked League of Legends games.

## Requirements
[`lol_id_tools`](https://github.com/mrtolkien/lol_id_tools), 
[`pandas`](https://pandas.pydata.org/), and 
[`riotwatcher`](https://github.com/pseudonym117/Riot-Watcher), as well as their
requirements.

Run `pip install -r requirements.txt` to automatically install all of them.

## Use
Run `python collect_ranked_stats.py {region name} {summoner name}`.

Example: `python collect_ranked_stats.py NA1 Zenîth`