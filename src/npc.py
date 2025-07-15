from agent import Agent
from llm import LLM
import time
import random

class NPC(Agent):
    def __init__(self, name, personality):
        super().__init__(name)
        self.personality = personality
        self.memory = ""
        self.llm = LLM()

    def run(self):
        self.connect()

        while True:
            time.sleep(random.randint(5,15))
            if self.conn.poll():
                msg = self.conn.recv()
                self.memory = self.memory + msg + '\n'

            log = "No messages! Say hello!"
            if self.memory != "":
                log = self.memory

            prompt = f"The current chat log contains:\n{log}\n---------\n"
            prompt = prompt + f"Your username is {self.name}\n"
            prompt = prompt + f"Your personality is {self.personality}\n\n"
            prompt = prompt + f"Respond in one sentence, and do not include your username in the message, the system will handle that. Do not respond to yourself. Keep your personality in mind when chatting."

            response = self.llm.prompt(prompt)
            output = response.output_text
            if output.startswith(self.name):
                output = output[len(self.name):-1]    


            self.conn.send(output)

            #print(prompt)


def create_npc(personality):
    llm = LLM()
    prompt = f"Your personality is {personality}. Choose a username for yourself, your output must be one word only with no extraneous symbols."
    response = llm.prompt(prompt)
    name = response.output_text
    return NPC(name, personality)


if __name__ == "__main__":
    npc = create_npc("grumpy")
    npc2 = create_npc("silly")
    npc3 = create_npc("confrontational")

    npc.start()
    time.sleep(1)
    npc2.start()
    time.sleep(2)
    npc3.start()