from actor import ActorMessage
import json


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


def load_room(path) -> Room | None:
    try:
        with open(path) as json_file:
            f = json.load(json_file)

        return Room(f["name"], f["description"])
    except:
        return None