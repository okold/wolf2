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
    def __init__(self, name = "Test Room", description = "A dark, empty void"):
        self.name = name
        self.description = description
        self.actors = {}

    def state(self):
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