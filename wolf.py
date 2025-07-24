
from multiprocessing import Process, Pipe
import random
import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from npc import NPC
from world import World
from llm import LLM



if __name__ == "__main__":

    # create players
    mick = NPC("Mick", "stoic, speaks only when necessary", "keep order in your bar, keep outlaws out NO OUTLAWS, will attack if they don't leave voluntarily")
    robin = NPC("Robin", "grumpy, but with a good heart", "fight your headache, relax after a long day of work in the mines, stay in your bar stool")
    franklin = NPC("Franklin", "anxious, quick to leave", "start a new life, get a new job, hide the fact you have a bounty the next planet over")
    deadeye = NPC("Deadeye", "bold, with a bit too quick a trigger finger", "hunt bounties, make money")
    sandy = NPC("Sandy", "aggressive, a little unhinged", "rob the saloon, be the first to shoot someone")
    boof = NPC("Boof", "lazy and hungry dog", "protect the saloon") # TODO: optionally replace with human player

    # create and start server
    parent_conn, child_conn = Pipe()
    world = World(LLM(), child_conn)
    world.start()

    # start players
    mick.start()
    robin.start()
    boof.start()
    time.sleep(random.randint(30,60))
    franklin.start()
    time.sleep(random.randint(60,120))
    sandy.start()
    time.sleep(random.randint(30,120))
    deadeye.start()

    while True:
        msg = input()
        parent_conn.send(msg)
        if msg == "quit" or msg == "exit":
            break

    world.join()