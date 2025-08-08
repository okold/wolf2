# Wolf2

THIS IS UNDER CONSTRUCTION.

This is a game which pits LLMs against each other in the social deduction game Werewolf (or Mafia, or any of its other variants). It tests their roleplay capability and reasoning.

Right now, the game is configured to compare the difference between summarizing context managers and sliding window context managers.

It runs on a local machine with ollama, or through the openai API. 

## Installation

TODO: automate this

In the root folder, you'll need to create a configuration file in the config directory named **api.json**, which will read your LLM's API key.

```
{
    "model": "<model name>",
    "key": "<API key>"
}
```

TODO: venv creation?

### Pip Dependencies
- openai
- ollama

#### Models:
By default, the experiments use these models:

- **llama3.1:8b** for speech generation
- **llama4:16x17b** for summarization

But you can modify the configuration files to use any models you want.

## Running

To run an experiment:

```
python3 wolf2.py
```

Arguments (from least to most resouce-intensive):

```
-o  > online inference (openai API)
-ww > wolves window, villagers window
-sw > wolves summary, villagers window
-ws > wolves window, villagers summary
-ss > wolves summary, villagers summary

```

TODO: queue consecutive runs