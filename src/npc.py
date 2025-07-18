from actor import Actor
from llm import LLM
import time
import random
import json
import logging
import os
from datetime import datetime

def create_npc_logger(name: str, timestamp: datetime, log_dir: str = "logs") -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"{timestamp.strftime('%Y-%m-%d %H-%M-%S')} {name}.txt")
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:  # Avoid duplicate handlers on reload
        file_handler = logging.FileHandler(log_filename)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

class NPC(Actor):

    CONTEXT_LIMIT = 10
    CONTEXT_KEEP = 5
    WAIT_MIN = 5
    WAIT_MAX = 10

    SYSTEM_MESSAGE = """You are an actor in a role-playing system that functions like a chat room.
        Your output must be valid JSON. Example:
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
        self.last_summary = "My memories are fresh!"
        self.last_output = None

        timestamp = datetime.now()
        self.logger = create_npc_logger(name, timestamp)

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

        self.logger.info(f"{self.name} created a summary:\n{self.last_summary}")

        # trim old messages
        if len(self.context) >= NPC.CONTEXT_LIMIT:
            self.context = self.context[NPC.CONTEXT_LIMIT - NPC.CONTEXT_KEEP:]

    def run(self):
        self.connect()
        
        # main loop
        while True:
            new_messages = False
            try:
                self.logger.info(f"{self.name} is waiting for new messages")
                time.sleep(random.randint(NPC.WAIT_MIN, NPC.WAIT_MAX)) # to keep things from going too fast
                while self.conn.poll():
                    msg = self.conn.recv()
                    self.context.append(msg)
                    new_messages = True
                    self.logger.info(f"{self.name} received world message: {msg}")

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
                self.logger.info(f"{self.name} sending to LLM. Prompt:\n{prompt}")
                response = self.llm.prompt(prompt, json=True)
                output = response.output_text
                
                self.logger.info(f"{self.name} received LLM response:\n{output}")

                try:
                    output = json.loads(output)

                    if output == self.last_output and output["action"] != 'listen':
                        self.logger.warning(f"{self.name} is being repetitive.")
                    else:
                        self.context.append({"role": "assistant", "content": response.output_text})

                    if output["action"] == "think":
                        self.logger.info(f"{self.name} decided to think!")
                        self.summarize()

                    elif output["action"] == "leave":
                        self.logger.info(f"{self.name} decided to leave!")
                        break

                    elif output["action"] == 'listen':
                        self.logger.info(f"{self.name} decided to listen!")
                        pass

                    else:
                        self.logger.info(f"{self.name} sent to world: {output}")
                        self.conn.send(output)
                        

                except Exception as e:
                    self.logger.warning(e)

                # hit max window size
                if len(self.context) >= NPC.CONTEXT_LIMIT:
                    self.summarize()

        self.conn.close()
    
        
if __name__ == "__main__":

    mick = NPC("Mick", "stoic, speaks only when necessary", "keep order in your bar, keep outlaws out", cha=13)
    robin = NPC("Robin", "grumpy, but with a good heart", "fight your headache, relax after a long day of work in the mines, stay in your bar stool", cha=10)
    franklin = NPC("Franklin", "anxious, quick to leave", "lay low, hide the fact you have a bounty the next county over", cha=9)
    maverick = NPC("Deadeye", "bold, with a bit too quick a trigger finger", "hunt bounties, make money", cha=12)
    bandit = NPC("Sandy", "aggressive, a little unhinged", "rob the saloon, be the first to shoot someone", cha=11)

    try:
        mick.start()
        robin.start()
        time.sleep(random.randint(21,30))
        franklin.start()
        time.sleep(random.randint(30,42))
        bandit.start()
        time.sleep(random.randint(21,42))
        maverick.start()
    except ConnectionResetError as e:
        print("Server closed, all agents died.")