class Room():
    def __init__(self, name = "Mick's", description = "A western-style space saloon, right at the edge of the galaxy."):
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