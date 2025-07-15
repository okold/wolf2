from multiprocessing import Process
from threading import Thread, Lock
from multiprocessing.connection import Listener, Pipe
import time
import logging
from agent import Agent

ADDRESS = ("localhost", 6000)

class World(Process):
    def __init__(self, name = "Test Room", description = "A blank, dark void."):
        super().__init__()
        self.name = name
        self.description = description

        self.agents_lock = Lock()
        self.agents = {}

        self.listener = Listener(ADDRESS)

    def try_recv(self, conn):
        try:
            if conn.poll():
                return conn.recv()
        except EOFError:
            pass

        return False

    def run(self):
        def listen_loop():
            while True:
                # waits here until there's a connection
                conn = self.listener.accept()

                self.agents_lock.acquire()
                name = conn.recv()
                self.agents[name] = conn
                print(f"{name} has connected!")
                self.agents_lock.release()

        listener_thread = Thread(target=listen_loop, daemon=True)
        listener_thread.start()

        # Keep the main run method alive (you can add other world logic here)
        while True:
            self.agents_lock.acquire()
            for agent in self.agents:
                msg = self.try_recv(self.agents[agent])
                if msg:
                    print(f"{agent}: {msg}")
                    for agent2 in self.agents:
                        #if agent2 != agent:
                        self.agents[agent2].send(f"{agent}: {msg}")

            self.agents_lock.release()

if __name__ == "__main__":
    world = World()
    world.start()