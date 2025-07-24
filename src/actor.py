from multiprocessing.connection import Client
from multiprocessing import Process
import time
from pydantic import BaseModel
from typing import Optional

ADDRESS = ("localhost", 6000)

# TODO: update this...
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
    description: str
    status: Optional[str]
    strength: Optional[int]
    intelligence: Optional[int]
    charisma: Optional[int]
    luck: Optional[int]


class Actor(Process):
    """
    An Actor that can connect to a World.

    Args:
        name (str): the actor's name
        personality (str): a description of the actor's personality
        goal (str): a description of the actor's primary goal
        description(Optional[str]): the actor's physical description
        status (Optional[str]): dead/alive status of the actor
        strength (Optional[int]): affects physical skill checks
        intelligence (Optional[int]): affects knowledge-based skill checks
        charisma (Optional[int]): affects speaking priority
        luck (Optional[int]): affects various things
        can_speak (Optional[int]): default True
    """
    def __init__(self, name, personality, goal, description = "The most generic person imaginable.", status = "alive", strength = 10, intelligence = 10, charisma = 10, luck = 10, can_speak = True):
        super().__init__()

        self.name = name
        self.personality = personality
        self.goal = goal
        self.status = status
        self.description = description
        self.can_speak = can_speak

        self.strength = strength # feats of physical prowess
        self.intelligence = intelligence # knowing things
        self.charisma = charisma # trade, convincing others
        self.luck = luck # for gambling, etc

        # affects random rolls
        self.lck_mod = luck - 10
        self.int_mod = intelligence - 10

        self.conn = None
        self.room_info = {}

    def dict_server(self) -> ActorMessage:
        """
        Returns an ActorMessage containing the name, status, and stats of the Actor.
        """
        return {
            "name": self.name,
            "description": self.description,
            "can_speak": self.can_speak,
            "status": self.status,
            "strength": self.strength,
            "intelligence": self.intelligence,
            "charisma": self.charisma,
            "luck": self.luck
        }
    
    def dict_public(self) -> ActorMessage:
        """
        Returns an ActorMessage containing the name and status of the Actor.
        """
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status
        }

    def character_sheet(self) -> str:
        """
        Returns a character sheet, for use in LLM contexts.
        """

        desc = f"""--CHARACTER SHEET--
        Your name is: {self.name}
        Your description is: {self.description}
        Your personality is: {self.personality}
        Your goal is: {self.goal}
        Your character is capable of speech: {self.can_speak}

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
            desc += f" {actor}: {self.description} ({self.room_info['actors'][actor]['status']})"

        desc += "---"

        return desc

    ## connect()
    # TODO: error handling on messages, success codes
    def connect(self):
        """
        Attempts to connect to the server five times, then gives up.
        """
        attempt_counter = 5

        while self.conn == None and attempt_counter > 0:
            try:    
                self.conn = Client(ADDRESS)
            except ConnectionRefusedError:
                time.sleep(1)
                attempt_counter -= 1    
       
        if self.conn != None:
            self.conn.send(self.dict_server()) # sends actor info to the server

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