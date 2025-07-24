
from multiprocessing import Process, Pipe
import random
import time
import sys
import os
import csv

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from npc import NPC
from world import World
from llm import LLM

NPCS_PATH = "npcs.csv"


if __name__ == "__main__":


    player_list = []

    with open(NPCS_PATH, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        npc_list = [row for row in reader]

    # create and start server
    parent_conn, child_conn = Pipe()
    world = World(LLM(), child_conn)
    world.start()

    print("Spawning bots...")
    for npc in npc_list:
        #print(npc)
        
        if npc["can_speak"].upper() == "TRUE":
            npc["can_speak"] = True
        else:
            npc["can_speak"] = False

        bot_player= NPC(npc["name"], npc["personality"], npc["goal"], npc["description"], npc["can_speak"], npc["gender"])
        bot_player.start()
        player_list.append(bot_player)

        #time.sleep(random.randint(5,60))



    print("Done spawning bots, CLI free.")


    while True:
        msg = input()
        parent_conn.send(msg)
        if msg == "quit" or msg == "exit":
            break

    for bot in player_list:
        bot.kill()


