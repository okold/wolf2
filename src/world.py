from multiprocessing import Process, Pipe
from threading import Thread, Lock
from multiprocessing.connection import Listener, Pipe
import time
import logging
from actor import Actor
import random

ADDRESS = ("localhost", 6000)

### World
# The main server process for the game. Can receive messages from the 
class World(Process):

    WAIT_TIME = 2

    def __init__(self, cli, default_room = None):
        super().__init__()

        # for cli
        self.cli = cli

        # actors and connection stuff
        self.actors_lock = Lock()
        self.actors = {}
        self.listener = Listener(ADDRESS)

        if default_room == None:
            self.default_room = Room()
        else:
            self.default_room = default_room

        print(f"Current Room: {self.default_room.name}")
        print(self.default_room.description)

    # safely attempts a recv from the provided connection
    def try_recv(self, conn):

        try:
            logging.info(F"Attempting to poll {conn}.")
            if conn.poll():
                response = conn.recv()
                logging.info(response)
                return response
            return None
        except:
            #logging.error("Failed to poll connection, returning leave message for actor.")
            return {"action": "leave"}
        
    def run(self):

        # thread for new connections
        # the actor's next message after accepting must be the desired name
        # for now, closes connection if the name is a duplicate
        def listen_loop():
            while True:
                conn = self.listener.accept()

                self.actors_lock.acquire()

                actor = conn.recv()

                if actor["name"] in self.actors:
                    conn.close() # TODO: error response for retries
                else:

                    self.actors[actor["name"]] = actor
                    actor["conn"] = conn
                    conn.send(self.default_room.dict())

                    for to_msg in self.actors:
                        self.actors[to_msg]["conn"].send({"role": "user", "content": f"{actor['name']} has entered the room!"})
                    print(f"{actor['name']} has entered the room!")
                
                self.actors_lock.release()

        listener_thread = Thread(target=listen_loop, daemon=True)
        listener_thread.start()

        # main loop
        while True:
            # check for cli messages
            msg = self.try_recv(self.cli)
            if msg == "quit" or msg == "exit":
                break

            flagged_actors = [] # flag bad connections for removal

            # check each actor for messages & forward
            self.actors_lock.acquire()

            for actor in self.actors:
                msg = self.try_recv(self.actors[actor]["conn"])
                if msg == None:
                    pass

                ### speak
                # { "action": "speak", "content": "I am saying something!"}
                # Echoes the content to the rest of the room.
                elif msg["action"] == "speak":
                    output = f"{actor}: {msg['content']}"
                    print(output)
                    for agent2 in self.actors:
                        if agent2 != actor:
                            self.actors[agent2]["conn"].send({"role": "user", "content": output})


                ### give
                # { "action": "give", "content": "whiskey", "target": "Bandit" }
                # TODO: an ACTUAL inventory system. for now, it's just pretend. for fun.
                elif msg["action"] == "give":
                    print(msg)
                    output = f"{actor} gave a(n) {msg['content']} to {msg['target']}"
                    print(output)
                    for agent2 in self.actors:
                            self.actors[agent2]["conn"].send({"role": "user", "content": output})

                ### challenge
                # { "action": "challenge", "content": "dance", "target": "Bandit"}
                # TODO: STUB
                elif msg["action"] == "challenge":
                    pass

                ### leave
                # { "action": "leave" }
                # Flags the requesting actor for clearing.
                elif msg["action"] == "leave":
                    flagged_actors.append((actor, "left"))

                ### shoot
                # { "action": "shoot", "target": "Bandit", "reason": "Enforcing the law." }
                # Shooting the target has a 1/2 chance of success.
                # Killed targets will be flagged for removal.
                elif msg["action"] == "shoot":
                    try:
                        roll = random.randint(1,20)
                        if roll >= 10:
                            output = f"{actor} has shot {msg['target']}, and hit!"
                            flagged_actors.append((msg["target"], "killed"))
                            for agent2 in self.actors:
                                if agent2 != actor:
                                    self.actors[agent2]["conn"].send({"role": "user", "content": output})
                                else:
                                    self.actors[agent2]["conn"].send({"role": "assistant", "content": f"I shot {msg['target']}, and hit!"})
                        else:
                            output = f"{actor} has shot {msg['target']}, and missed!"
                            for agent2 in self.actors:
                                if agent2 != actor:
                                    self.actors[agent2]["conn"].send({"role": "user", "content": output})
                                else:
                                    self.actors[agent2]["conn"].send({"role": "assistant", "content": f"I shot {msg['target']}, and missed!"})
                        print(output + f"SERVER--Reason: {msg['reason']}")
                    except:
                        pass

            # cleans up flagged actors
            for actor in flagged_actors:
                try:
                    self.actors[actor[0]]["conn"].close()
                    self.actors.pop(actor[0], None)

                    if actor[1] == "killed":
                        msg = f"{actor[0]} has been killed!"
                    else:
                        msg = f"{actor[0]} has left the room!"

                    print(msg)

                    for agent2 in self.actors:
                        self.actors[agent2]["conn"].send({"role": "user", "content": msg})
                except:
                    pass


            self.actors_lock.release()
            time.sleep(World.WAIT_TIME)

class Room():
    def __init__(self, name = "Mick's", description = "A western-style saloon."):
        self.name = name
        self.description = description
        self.actors = []

    def dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "actors": self.actors
        }
    
    def add_actor(self, name):
        self.actors.append(name)

    def remove_actor(self, name):
        self.actors.pop(name, None)

    

if __name__ == "__main__":
    parent_conn, child_conn = Pipe()
    world = World(child_conn)
    world.start()

    while True:
        msg = input()
        parent_conn.send(msg)
        if msg == "quit" or msg == "exit":
            break

    world.join()