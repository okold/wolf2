class SpeakingContest():
    def __init__(self):
        self.max_cha = 0
        self.speak_output = None
        self.speak_actor = None
        self.interrupted_actors = []

    def add_speaker(self, actor, speech, charisma):
        if charisma > self.max_cha:
            self.speak_output = {"role": "user", "content": f"{actor} says, \"{speech}\""}
            self.max_cha = charisma

            if self.speak_actor != None:
                self.interrupted_actors.append(self.speak_actor)

            self.speak_actor = actor
        else:
            self.interrupted_actors.append(actor)