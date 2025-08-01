from colorama import Style

class SpeakingContest():
    def __init__(self):
        self.max_cha = 0
        self.speak_output_colour = None
        self.speak_output_plain = None
        self.speak_actor = None
        self.interrupted_actors = []

    def add_speaker(self, actor, speech, charisma, colour = None):
        if charisma > self.max_cha:

            self.speak_output_plain = {"role": "user", "content": f"{actor} says, \"{speech}\""}

            if colour:
                self.speak_output_colour = {"role": "user", "content": colour + actor + Style.RESET_ALL + f" says, \"{speech}\""}
                
            self.max_cha = charisma

            if self.speak_actor != None:
                self.interrupted_actors.append(self.speak_actor)

            self.speak_actor = actor
        else:
            self.interrupted_actors.append(actor)
            

    def resolve(self):
        return self.speak_output_plain, self.speak_output_colour, self.speak_actor, self.interrupted_actors