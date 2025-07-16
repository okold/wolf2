from multiprocessing.connection import Client
from multiprocessing import Process
import time

ADDRESS = ("localhost", 6000)

class Actor(Process):
    def __init__(self, name, personality, goal, str = 10, int = 10, cha = 10, lck = 10):
        super().__init__()

        self.name = name
        self.personality = personality
        self.goal = goal

        self.str = str # feats of physical prowess
        self.int = int # knowing things
        self.cha = cha # trade, convincing others
        self.lck = lck # for gambling, etc

        self.conn = None
        self.room_info = {}

    def dict(self):
        return {
            "name": self.name,
            "str": self.str,
            "int": self.int,
            "cha": self.cha,
            "lck": self.lck
        }

    def character_sheet(self):
        return f"""--CHARACTER SHEET--
        Your name is: {self.name}
        Your personality is: {self.personality}
        Your goal is: {self.goal}

        STATS (10 is average): 
        Strength:       {self.str}
        Intelligence:   {self.int}
        Charisma:       {self.cha}
        Luck:           {self.lck}

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
        self.conn.send(self.dict()) # sends actor info to the server

        try:
            self.room_info = self.conn.recv() # receives environmental info
        except EOFError:
            pass

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