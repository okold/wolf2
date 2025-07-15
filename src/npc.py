from actor import Actor
from llm import LLM
import time
import random
import json

class NPC(Actor):

    CONTEXT_LIMIT = 20

    SYSTEM_MESSAGE = """You are an actor in a role-playing system that functions like a chat room.
    Your output must be in valid JSON format:
        { "action": <action_name>, "content": <varies_by_action>, "target": <name>, "reason": <text> }

    Available actions are:
        - speak: whatever you say will be broadcast to others in the room.
        Example: { "action": "speak", "content": "I am saying something!"}

        - shoot: shoot another player, giving them a 1/2 chance of being forcibly removed from the room.
        Example: { "action": "shoot", "target": "Bandit", "reason": "Enforcing the law" }

        - leave: you will disconnect from the system
        Example: { "action": "leave" }

    Stay in character. Only act from your own perspective. Try to inject something new into the conversation.
    """

    def __init__(self, name, personality, goal):
        super().__init__(name, personality, goal)
        self.context = []
        self.llm = LLM()

    def summarize(self):
        prompt = [
                {"role": "developer", "content": "You are an actor in a role-playing system that functions like a chat room. Summarize the following log, making note of all major events, and how your character feels about the others. Keep your summary in-character and in first person. This is your character sheet:" + self.character_sheet()}
            ] + self.context
        
        response = self.llm.prompt(prompt)

        print("-------------")
        print(f"summary for {self.name}:")
        print(response.output_text)
        print("-------------")

        self.context = [
            {"role": "developer", "content": f"IN-CHARACTER MEMORY:\n{response.output_text}"}
            ]

    def run(self):
        self.connect()

        # main loop
        while True:
            try:
                time.sleep(random.randint(10,20)) # to keep things from going too fast
                while self.conn.poll():
                    msg = self.conn.recv()
                    self.context.append(msg)
            except EOFError:
                break

            prompt = [
                {"role": "developer", "content": NPC.SYSTEM_MESSAGE + self.character_sheet()}
            ] + self.context

            if self.context == []:
                prompt.append(
                    {"role": "developer", "content": "No messages! Say hello!"}
                )

            while True:
                response = self.llm.prompt(prompt, json=True)

                output = response.output_text
                #print(output)

                try:
                    output = json.loads(output)

                    if output["action"] == "leave":
                        break

                    elif output["action"] == "shoot":
                        pass

                    else: 
                        self.context.append(
                            {"role": "assistant", "content": f"You: {output['content']}"}
                        )

                    self.conn.send(output)
                    break
                except:
                    print("-------------")
                    print("json.loads() failed. Output:")
                    print(output)
                    print("-------------")
            
            if len(self.context) >= NPC.CONTEXT_LIMIT:
                self.summarize()

        self.conn.close()
        print(f"{self.name} disconnected!")
            #print(prompt)
    

def create_npc(personality, goal):
    llm = LLM()
    prompt = f"Your personality is {personality}. Choose a western-style name for yourself, your output must be one word only with no extraneous symbols."
    response = llm.prompt(prompt)
    name = response.output_text
    print(name)
    return NPC(name, personality, goal)


if __name__ == "__main__":

    personalities = [
        ("grumpy", "have a strong drink" ), 
        ("silly", "cause chaos"),
        ("confrontational", "defend your honour"),
        ("flirty", "make friends"),
        ("greedy", "make money")
    ]

    for personality in personalities:
        npc = create_npc(personality[0], personality[1])
        npc.start()
        time.sleep(random.randint(1,10))