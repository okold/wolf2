from multiprocessing.connection import Pipe
from datetime import datetime
import csv
from multiprocessing.connection import Listener
import sys
import os
import json
import time
import random

sys.path.append(os.path.join(os.path.dirname(__file__), 'game'))
from wolfworld import WolfWorld
from wolflogger import WolfLogger
from wolfnpc import WolfNPC

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from utils import create_logger

NPCS_PATH = "game/npcs.csv"

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
    
    if "-r" in sys.argv:
        try:
            loop_count = int(sys.argv[sys.argv.index("-r") + 1])
        except (IndexError, ValueError):
            print("Error: -r must be followed by an integer.")
            sys.exit(1)
    else:
        loop_count = 1


    config = json.load(json_file)
    json_file.close()

    sys_message_file = "npc_system_message_turn_based.txt"

    player_list = []

    with open(NPCS_PATH, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        npc_list = [row for _, row in zip(range(WolfWorld.PLAYER_COUNT), reader)]

    for run_num in range(1,loop_count+1):
        timestamp = datetime.now()
        ts_int = int(timestamp.strftime('%Y%m%d%H%M%S'))
        random.seed(ts_int)

        csv_logger = WolfLogger(experiment, seed=ts_int)
        txt_logger = create_logger("World", seed=ts_int)


        # create and start server
        parent_conn, child_conn = Pipe()
        listener = Listener(("localhost", 0))

        world = WolfWorld(cli=child_conn, 
                          csv_logger=csv_logger,
                          txt_logger=txt_logger,
                          wolf_strategy=config["wolf_strategy"], 
                          village_strategy=config["village_strategy"],
                          seed=ts_int,
                          listener=listener)
        world.start()

        for npc in npc_list:
            #self.log(npc)
            if not isinstance(npc["can_speak"], bool):
                if npc["can_speak"].upper() == "TRUE":
                    npc["can_speak"] = True
                else:
                    npc["can_speak"] = False

            bot_player = WolfNPC(name=npc["name"],
                                 personality=npc["personality"],
                                 description=npc["description"],
                                 gender=npc["gender"],
                                 game_model=config["game_model"],
                                 summary_model=config["summary_model"],
                                 logger=txt_logger,
                                 csv_logger=csv_logger,
                                 seed=ts_int,
                                 address=listener.address
                                 )
            bot_player.start()
            player_list.append(bot_player)

        world.join()

