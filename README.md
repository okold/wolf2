# Wolf2

Right now, this program generates surreal space saloon stories in a chatroom-like format. Example output can be seen in the examples/ directory.

## Installation
In the root folder, you'll need to create a configuration file named **api.json**, which will read your LLM's API key.

```
{
    "model": "<model name>",
    "key": "<API key>"
}
```

### Dependencies
- openai


## Running

**world.py** is the game server. It will automatically write all messages to the logs/ directory.

*Note: might need to make the logs folder manually? Need to check this.*

Run it in the command line with:
```
python3 src/world.py
```

**npc.py** has a script to launch a few LLM-powered agents:

```
python3 src/npc.py
```

**player.py** enables the user to interact with the agents in the world.

*Note: the player cli hasn't been updated entirely with the new messaging system that enabled agent actions, so don't use it in this version.*

```
python3 src/player.py
```

## TODO
- Log actor summaries
- Fix repetition
- Make memory management more modular, decouple from npc class
- Saving preset actor profiles and rooms
- LLM options, turning model into an argument?
- GUI
- Documentation

## Debugging
If ports remain open when testing, until I have everything exit gracefully:
```
netstat -tulpn
kill <pid>
```