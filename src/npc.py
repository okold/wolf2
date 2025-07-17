from actor import Actor
from llm import LLM
import time
import random
import json

class NPC(Actor):

    CONTEXT_LIMIT = 10
    CONTEXT_KEEP = 5
    WAIT_MIN = 5
    WAIT_MAX = 5

    SYSTEM_MESSAGE = """You are an actor in a role-playing system that functions like a chat room.
    Your output must be in valid JSON format:
        { "action": <action_name>, "content": <varies_by_action>, "target": <name> }

    Available actions are:
        - speak: whatever you say will be broadcast to others in the room. If two people try to speak at once, one may be interrupted.
        Example: { "action": "speak", "content": "I am saying something."}

        - yell: messages will always go through
        Example: { "action": "yell", "content": "HANDS IN THE AIR! THIS IS A HOLD-UP!" }

        - listen: do nothing, waiting for more messages
        Example: { "action": "listen" }

        - give: give the target an item
        Example: { "action": "give", "content": "whiskey", "target": "Bandit" }

        - shoot: shoot another actor, with a 1/2 success chance
        Example: { "action": "shoot", "target": "Bandit" }

        - leave: if you do not wish to participate anymore
        Example: { "action": "leave" }

    Stay in character. Only act from your own perspective. Try to inject something new into the conversation.

    --LAST SUMMARY--
    """

    def __init__(self, name, personality, goal, str = 10, int = 10, cha = 10, lck = 10):
        super().__init__(name, personality, goal, str, int, cha, lck)
        self.context = []
        self.llm = LLM()
        self.last_summary = "Your memories are fresh!"
        self.last_output = None

    def summarize(self):
        prompt = self.context + [ 
                {"role": "developer", "content": f"""Summarize the above log. Older messages will be deleted.
                 Make note how your character feels about the others. 
                 Keep your summary in-character and in first person. You are {self.name}, and your personality is {self.personality}
                 Consider what you would like your next actions to be. Your primary goal is: {self.goal}
                 """}
                ]
        
        response = self.llm.prompt(prompt)
        self.last_summary = response.output_text

        print("-------------")
        print(f"Summary for {self.name}:")
        print(self.last_summary)
        print("-------------")

        # trim old messages
        if len(self.context) >= NPC.CONTEXT_LIMIT:
            self.context = self.context[NPC.CONTEXT_LIMIT - NPC.CONTEXT_KEEP:]

    def run(self):
        self.connect()

        can_think = True
        
        # main loop
        while True:
            new_messages = False
            try:
                time.sleep(random.randint(NPC.WAIT_MIN, NPC.WAIT_MAX)) # to keep things from going too fast
                while self.conn.poll():
                    msg = self.conn.recv()
                    self.context.append(msg)
                    new_messages = True

            except EOFError:
                break

            if new_messages:
                prompt = [
                    {"role": "developer", "content": NPC.SYSTEM_MESSAGE + "\n" + self.last_summary + "\n" + self.character_sheet()}
                ] + self.context

                if self.context == []:
                    prompt.append(
                        {"role": "developer", "content": "No messages! Say hello!"}
                    )

                response = self.llm.prompt(prompt, json=True)
                output = response.output_text
                #print(output)

                try:
                    output = json.loads(output)

                    if output == self.last_output:
                        print(f"{self.name} is being repetitive.")

                    if output["action"] == "think" and can_think:
                        print(f"{self.name} has decided to think!")
                        self.summarize()
                        can_think = False

                    elif output["action"] == "leave":
                        break

                    elif output["action"] == 'listen':
                        print(f"{self.name} has decided to listen.")
                        pass

                    else:
                        self.conn.send(output)
                        self.last_output = output

                    if output["action"] != "think":
                        can_think = True

                except Exception as e:
                    print("-------------")
                    print(e)
                    print("-------------")

                # hit max window size
                if len(self.context) >= NPC.CONTEXT_LIMIT:
                    self.summarize()

        self.conn.close()
        print(f"{self.name} disconnected!")
            #print(prompt)
    
        
if __name__ == "__main__":

    mick = NPC("Mick", "stoic", "keep order in your bar", 14, 10, 11, 8)
    robin = NPC("Robin", "grumpy", "fight your headache", 7, 11, 10, 10)
    franklin = NPC("Franklin", "anxious", "stay alive", 9, 12, 8, 15)
    maverick = NPC("Maverick", "bold", "hunt bounties", 14, 10, 11, 9)
    bandit = NPC("Jim the Outlaw", "aggressive", "rob the saloon", 13, 8, 15, 10)

    mick.start()
    time.sleep(5)
    robin.start()
    time.sleep(random.randint(30,60))
    franklin.start()
    time.sleep(random.randint(30,60))
    bandit.start()