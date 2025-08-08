from multiprocessing.connection import Pipe
from wolfworld import WolfWorld, WolfLogger
from wolfnpc import WolfNPC
import csv
import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), 'game'))
from llm import LLM

NPCS_PATH = "npcs.csv"

if __name__ == "__main__":

    
    if "-ww" in sys.argv:
        json_file = open("config/window-window.json")
        experiment = "ww"
    elif "-ss" in sys.argv:
        json_file = open("config/summary-summary.json")
        experiment = "ss"
    elif "-sw" in sys.argv:
        json_file = open("config/summary-window.json")
        experiment = "sw"
    elif "-ws" in sys.argv:
        json_file = open("config/window-summary.json")
        experiment = "ws"
    elif "-o" in sys.argv:
        json_file = open("config/online.json")
        experiment = "o"
    else:
        json_file = open("config/fast.json")
        experiment = "test"
    

    config = json.load(json_file)
    json_file.close()

    if config["cloud"] == True:
        sys_message_file = "npc_system_message_real_time.txt"
    else:
        sys_message_file = "npc_system_message_turn_based.txt"

    player_list = []

    with open(NPCS_PATH, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        npc_list = [row for _, row in zip(range(WolfWorld.PLAYER_COUNT), reader)]

    csv_logger = WolfLogger(config["model"], experiment)

    # create and start server
    parent_conn, child_conn = Pipe()
    world = WolfWorld(cli=child_conn, turn_based=(not config["cloud"]), csv_logger=csv_logger, wolf_strategy=config["wolf_strategy"], village_strategy=config["village_strategy"])
    world.start()

    llm = LLM(model=config["model"], cloud = config["cloud"])

    for npc in npc_list:
        #self.log(npc)
        
        if npc["can_speak"].upper() == "TRUE":
            npc["can_speak"] = True
        else:
            npc["can_speak"] = False

        bot_player= WolfNPC(npc["name"], npc["personality"], npc["goal"], npc["description"], npc["can_speak"], npc["gender"], llm, (not config["cloud"]), sys_message_file, None, csv_logger)
        bot_player.start()
        player_list.append(bot_player)

        #time.sleep(random.randint(5,60))



    world.join()

