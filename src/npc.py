from actor import Actor
from llm import LLM
import time
import random
import json

class NPC(Actor):

    CONTEXT_LIMIT = 20
    CONTEXT_KEEP = 10
    WAIT_MIN = 5
    WAIT_MAX = 10

    SYSTEM_MESSAGE = """You are an actor in a role-playing system that functions like a chat room.
    Your output must be in valid JSON format:
        { "action": <action_name>, "content": <varies_by_action>, "target": <name>, "reason": <text> }

    Available actions are:
        - speak: whatever you say will be broadcast to others in the room.
        Example: { "action": "speak", "content": "I am saying something!"}

        - think: do nothing, but process your context and consider your next action.
        Example: { "action": "think" }

        - give: give the target an item
        Example: { "action": "give", "content": "whiskey", "target": "Bandit" }

        - shoot: shoot another player, giving them a 1/2 chance of being forcibly removed from the room.
        Example: { "action": "shoot", "target": "Bandit", "reason": "Enforcing the law" }

        - leave: you will disconnect from the system
        Example: { "action": "leave" }

    Stay in character. Only act from your own perspective. Try to inject something new into the conversation.

    --LAST SUMMARY--
    """

    def __init__(self, name, personality, goal):
        super().__init__(name, personality, goal)
        self.context = []
        self.llm = LLM()
        self.last_summary = "Your memories are fresh!"

    def summarize(self):
        prompt = self.context + [ 
                {"role": "developer", "content": f"""Summarize the above log. Older messages will be deleted.
                 Make note how your character feels about the others. 
                 Keep your summary in-character and in first person. You are {self.name}
                 Consider what you would like your next actions to be.
                 """}
                ]
        
        response = self.llm.prompt(prompt)
        self.last_summary = response.output_text

        print("-------------")
        print(f"Summary for {self.name}:")
        print(self.last_summary)
        print("-------------")

        # trim old messages
        if len(self.context) > NPC.CONTEXT_KEEP:
            self.context = self.context[NPC.CONTEXT_KEEP:]

        print(self.context)

    def run(self):
        self.connect()

        # main loop
        while True:
            try:
                time.sleep(random.randint(NPC.WAIT_MIN, NPC.WAIT_MAX)) # to keep things from going too fast
                while self.conn.poll():
                    msg = self.conn.recv()
                    self.context.append(msg)

            except EOFError:
                break

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

                if output["action"] == "leave":
                    break

                elif output["action"] == "shoot":
                    pass

                elif output["action"] == "think":
                    print(f"{self.name} has decided to think!")
                    self.summarize()

                elif output["action"] == "give":
                    pass

                else: 
                    self.context.append(
                        {"role": "assistant", "content": f"You: {output['content']}"}
                    )

                self.conn.send(output)

            except:
                print("-------------")
                print("json.loads() failed. Output:")
                print(output)
                print("-------------")
            
            
            # hit max window size
            if len(self.context) >= NPC.CONTEXT_LIMIT:
                self.summarize()

        self.conn.close()
        print(f"{self.name} disconnected!")
            #print(prompt)
    
## personality: (personality, goal)
def create_npc(personality):
    llm = LLM()
    prompt = f"""Your personality is {personality[0]}.
    Your main goal is: {personality[1]}. 
    Choose a western-style name for yourself.
    Your output must be one word with no symbols or punctuation."""

    response = llm.prompt(prompt)
    name = response.output_text
    print(name)
    slices = name.split(' ')
    name = slices[-1]
    
    name = name.replace('"', "")
    name = name.replace('!', "")
    name = name.replace('.', "")
    return NPC(name, personality[0], personality[1])
        


if __name__ == "__main__":

    personalities = [
        ("grumpy", "fight your headache" ), 
        ("whimsical", "enable chaos"),
        ("confrontational", "defend your honour")
    ]

    mick = NPC("Mick", "gruff", "keep order in your bar")
    bandit = NPC("Bandit", "aggressive", "be the first to shoot someone, be dramatic!")

    mick.start()

    for personality in personalities:
        npc = create_npc(personality)
        npc.start()
        time.sleep(random.randint(10,20))


    time.sleep(random.randint(30,60))
    bandit.start()