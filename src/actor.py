from multiprocessing.connection import Client
from multiprocessing import Process
import time

ADDRESS = ("localhost", 6000)

class Actor(Process):
    def __init__(self, name, personality, goal):
        super().__init__()
        self.name = name
        self.personality = personality
        self.goal = goal

        self.conn = None
        self.room_info = {}

    def character_sheet(self):
        return f"""--CHARACTER SHEET--
        Your name is: {self.name}
        Your personality is: {self.personality}
        Your goal is: {self.goal}
        You are currently in a room named: {self.room_info['name']}
        The room's description is: {self.room_info['description']}
        ----"""

    ## connect()
    # TODO: error handling on messages, success codes
    def connect(self):
        while self.conn == None:
            try:    
                self.conn = Client(ADDRESS)
            except ConnectionRefusedError:
                time.sleep(1)    
        self.conn.send(self.name)         # sends name

        try:
            self.room_info = self.conn.recv() # receives environmental info
        except EOFError:
            self.kill()

    ## run()
    # STUB. Implemented in Player and NPC
    def run(self):
        self.connect()

        while True:
            pass

if __name__ == "__main__":
    bob = Actor("Bob")

    bob.start()

    time.sleep(3)

    alice = Actor("Alice")
    alice.start()

    bob.join()
    alice.join()