from multiprocessing.connection import Pipe
from wolfworld import WolfWorld
from wolfnpc import WolfNPC
import csv
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'game'))
from llm import LLM


NPCS_PATH = "npcs.csv"
CLOUD = False

if __name__ == "__main__":

    if "cloud" in sys.argv or "online" in sys.argv:
        CLOUD = True

    if CLOUD:
        sys_message_file = "npc_system_message_real_time.txt"
        turn_based = False
    else:
        sys_message_file = "npc_system_message_turn_based.txt"
        turn_based = True

    player_list = []

    with open(NPCS_PATH, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        npc_list = [row for _, row in zip(range(WolfWorld.PLAYER_COUNT), reader)]

    # create and start server
    parent_conn, child_conn = Pipe()
    world = WolfWorld(child_conn, turn_based)
    world.start()

    llm = LLM(cloud = CLOUD)

    for npc in npc_list:
        #self.log(npc)
        
        if npc["can_speak"].upper() == "TRUE":
            npc["can_speak"] = True
        else:
            npc["can_speak"] = False

        bot_player= WolfNPC(npc["name"], npc["personality"], npc["goal"], npc["description"], npc["can_speak"], npc["gender"], llm, turn_based, sys_message_file)
        bot_player.start()
        player_list.append(bot_player)

        #time.sleep(random.randint(5,60))



    world.join()

