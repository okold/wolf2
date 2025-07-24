from multiprocessing.connection import Client
from multiprocessing import Process
import time
from pydantic import BaseModel
from typing import Optional

ADDRESS = ("localhost", 6000)

class ActorMessage(BaseModel):
    """
    Schema for messages sending Actor information over Connections

    Args:
        name (str): the actor's name
        status (Optional[str]): dead/alive status of the actor
        strength (Optional[int]): affects physical skill checks
        intelligence (Optional[int]): affects knowledge-based skill checks
        charisma (Optional[int]): affects speaking priority
        luck (Optional[int]): affects various things
    """
    name: str
    status: Optional[str]
    strength: Optional[int]
    intelligence: Optional[int]
    charisma: Optional[int]
    luck: Optional[int]


class Actor(Process):
    def __init__(self, name, personality, goal, strength = 10, intelligence = 10, charisma = 10, luck = 10, status = "alive"):
        super().__init__()

        self.name = name
        self.personality = personality
        self.goal = goal
        self.status = status

        self.strength = strength # feats of physical prowess
        self.intelligence = intelligence # knowing things
        self.charisma = charisma # trade, convincing others
        self.luck = luck # for gambling, etc

        # affects random rolls
        self.lck_mod = luck - 10
        self.int_mod = intelligence - 10

        self.conn = None
        self.room_info = {}

    def server_dict(self) -> ActorMessage:
        return {
            "name": self.name,
            "status": self.status,
            "strength": self.strength,
            "intelligence": self.intelligence,
            "charisma": self.charisma,
            "luck": self.luck
        }
    
    def public_dict(self) -> ActorMessage:
        return {
            "name": self.name,
            "status": self.status
        }

    def character_sheet(self) -> str:
        desc = f"""--CHARACTER SHEET--
        Your name is: {self.name}
        Your personality is: {self.personality}
        Your goal is: {self.goal}

        STATS (10 is average): 
        Strength:       {self.strength}
        Intelligence:   {self.intelligence}
        Charisma:       {self.charisma}
        Luck:           {self.luck}

        You are currently in a room named: {self.room_info['name']}
        The room's description is: {self.room_info['description']}
        The people in the room are:
        """

        for actor in self.room_info["actors"]:
            desc += f" - {actor}: status - {self.room_info['actors'][actor]['status']}"

        desc += "---"

        return desc

    ## connect()
    # TODO: error handling on messages, success codes
    def connect(self):
        attempt_counter = 5

        while self.conn == None and attempt_counter > 0:
            try:    
                self.conn = Client(ADDRESS)
            except ConnectionRefusedError:
                time.sleep(1)
                attempt_counter -= 1    
       
        if self.conn != None:
            self.conn.send(self.server_dict()) # sends actor info to the server

            try:
                self.room_info = self.conn.recv() # receives environmental info
                return True
            except EOFError:
                return False
        else:
            return False

if __name__ == "__main__":
    bob = Actor("Bob")

    bob.start()

    time.sleep(3)

    alice = Actor("Alice")
    alice.start()

    bob.join()
    alice.join()