from multiprocessing import Process, Pipe
from threading import Thread, Lock
from multiprocessing.connection import Listener, Pipe
import time
import logging
from actor import Actor
import random

ADDRESS = ("localhost", 6000)

class World(Process):
    def __init__(self, comm):
        super().__init__()

        # receives command line arguments
        self.comm = comm

        # client connection stuff
        self.agents_lock = Lock()
        self.agents = {}
        self.listener = Listener(ADDRESS)

        self.default_room = Room()

    # safely attempts a recv from the provided connection
    def try_recv(self, conn):
        try:
            if conn.poll():
                return conn.recv()
            return None
        except:
            return {"action": "leave"}
        
    def run(self):

        # thread for new connections
        # the agent's next message after accepting must be the desired name
        def listen_loop():
            while True:
                conn = self.listener.accept()
                self.agents_lock.acquire()

                name = conn.recv()

                if name in self.agents:
                    conn.close() # TODO: error response for retries
                else:
                    self.agents[name] = conn
                    conn.send(self.default_room.dict())

                    for agent in self.agents:
                        if agent != name:
                            self.agents[agent].send({"role": "user", "content": f"{name} has entered the room!"})
                    print(f"{name} has entered the room!")
                    self.agents_lock.release()

        listener_thread = Thread(target=listen_loop, daemon=True)
        listener_thread.start()

        # main loop
        while True:

            # check for cli messages
            msg = self.try_recv(self.comm)
            if msg == "quit" or msg == "exit":
                break

            # check each agent for messages & forward
            self.agents_lock.acquire()

            flagged_agents = [] # flag bad connections for removal

            for agent in self.agents:
                msg = self.try_recv(self.agents[agent])
                if msg:

                    if msg["action"] == "shoot":
                        try:
                            roll = random.randint(1,20)
                            if roll >= 10:
                                output = f"{agent} has shot {msg['target']}, and hit!"
                                flagged_agents.append((msg["target"], "killed"))
                                for agent2 in self.agents:
                                    if agent2 != agent:
                                        self.agents[agent2].send({"role": "user", "content": output})
                                    else:
                                        self.agents[agent2].send({"role": "assistant", "content": f"I shot {msg['target']}, and hit!"})
                            else:
                                output = f"{agent} has shot {msg['target']}, and missed!"
                                for agent2 in self.agents:
                                    if agent2 != agent:
                                        self.agents[agent2].send({"role": "user", "content": output})
                                    else:
                                        self.agents[agent2].send({"role": "assistant", "content": f"I shot {msg['target']}, and missed!"})
                            print(output + f"SERVER--Reason: {msg['reason']}")
                        except:
                            pass

                    if msg["action"] == "leave":
                        flagged_agents.append((agent, "left"))

                    if msg["action"] == "speak":
                        output = f"{agent}: {msg['content']}"
                        print(output)
                        for agent2 in self.agents:
                            if agent2 != agent:
                                self.agents[agent2].send({"role": "user", "content": output})
                        

            for agent in flagged_agents:
                try:
                    self.agents[agent[0]].close()
                    self.agents.pop(agent[0], None)

                    if agent[1] == "killed":
                        msg = f"{agent[0]} has been killed!"
                    else:
                        msg = f"{agent[0]} has left the room!"

                    print(msg)

                    for agent2 in self.agents:
                        self.agents[agent2].send({"role": "user", "content": msg})
                except:
                    pass


            self.agents_lock.release()

class Room():
    def __init__(self, name = "Mick's", description = "A western-style saloon."):
        self.name = name
        self.description = description

    def dict(self):
        return {
            "name": self.name,
            "description": self.description
        }

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