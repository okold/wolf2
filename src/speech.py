class SpeakingContest():
    def __init__(self, room):
        self.max_cha = 0
        self.speak_output = None
        self.speak_actor = None
        self.interrupted_actors = []
        self.room = room

    def add_speaker(self, actor, speech, charisma, room):
        if room == self.room:
            if charisma > self.max_cha:
                self.speak_output = {"role": "user", "content": f"{actor} says, \"{speech}\""}
                self.max_cha = charisma

                if self.speak_actor != None:
                    self.interrupted_actors.append(self.speak_actor)

                self.speak_actor = actor
            else:
                self.interrupted_actors.append(actor)

    def resolve(self):
        return self.speak_output, self.speak_actor, self.interrupted_actors