class Room():
    def __init__(self, name = "Mick's", description = "A western-style space saloon, right at the edge of the galaxy. The radio is playing cool jazz, and the lights are buzzing overhead. On the wall is a poster depicting current bounties, and right front and center you see: WANTED - SANDY THE OUTLAW - 50 MILLION DOUBLE-CREDITS - DEAD OR ALIVE"):
        self.name = name
        self.description = description
        self.actors = {}

    def dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "actors": self.actors
        }
    
    def add_actor(self, name, status = "alive"):
        self.actors[name] = {"name": name, "status": status}

    def kill_actor(self, name):
        if name in self.actors:
            self.actors[name]["status"] = "dead"

    def remove_actor(self, name):
        self.actors.pop(name, None)