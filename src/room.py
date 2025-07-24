from pydantic import BaseModel
from actor import ActorMessage

class RoomMessage(BaseModel):
    """
    Schema for sending room states between processes.

    Args:
        name (str): the name of the room
        description (str): the description of the rooms
        actors (dict[str, ActorMessage]): actor information broadcast to all
    """
    name: str
    description: str
    actors: dict[str, ActorMessage]

class Room():
    def __init__(self, name = "Mick's", description = "A western-style space saloon, right at the edge of the galaxy. The radio is playing cool jazz, and the lights are buzzing overhead. On the wall is a poster depicting current bounties, and right front and center you see: WANTED - SANDY THE OUTLAW - 50 MILLION DOUBLE-CREDITS - DEAD OR ALIVE"):
        self.name = name
        self.description = description
        self.actors = {}

    def dict(self) -> RoomMessage:
        return {
            "name": self.name,
            "description": self.description,
            "actors": self.actors
        }
    
    def add_actor(self, actor: ActorMessage):
        if actor["name"] not in self.actors:
            self.actors[actor["name"]] = actor

    def kill_actor(self, name):
        if name in self.actors:
            self.actors[name]["status"] = "dead"

    def remove_actor(self, name):
        self.actors.pop(name, None)