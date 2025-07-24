from actor import Actor
from context import SummaryContext
from llm import LLM
import time
import random
import json
import logging
import os
from datetime import datetime

def create_npc_logger(name: str, timestamp: datetime, log_dir: str = "logs") -> logging.Logger:
    """
    Creates a logger.

    Args:
        name (str): the name of the logger, appended to the end of the filename
        timestamp (datetime): placed at the head of the filename
        log_dir (str): directory of the log
    """
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

    WAIT_MIN_ABS = 5
    WAIT_MAX_ABS = 15

    SYSTEM_MESSAGE = """You are an actor in a role-playing system that functions like a chat room.
        Your output must be valid JSON. Example:
        { "action": <action_name>, "content": <varies_by_action>, "target": <name>, "comment": <additional_dialogue> }

    Available actions are:
        - speak: whatever you say will be broadcast to others in the room. If two people try to speak at once, one may be interrupted.
        Example: { "action": "speak", "content": "I am saying something."}

        - gesture: allows you to gesture
            - comment is optional
        Example: { "action": "gesture", "content": "throws her hands in the air" }
        Example: { "action": "gesture", "content": "points at the Bandit", "comment": "You're a wanted criminal!" }

        - yell: messages will always go through
        Example: { "action": "yell", "content": "HANDS IN THE AIR! THIS IS A STICK-UP!" }

        - listen: do nothing, waiting for more messages
        Example: { "action": "listen" }

        - give: give the target an item
            - comment is optional
            - gesture is optional
        Example: { "action": "give", "content": "side eye", "target": "Franklin" }
        Example: { "action": "give", "content": "battery", "target": "Lola", "gesture": "slides the battery across the counter" }
        Example: { "action": "give", "content": "whiskey", "target": "Bandit", "comment": "Here you go!" }

        - shoot: shoot another actor, with a 1/2 success chance
        Example: { "action": "shoot", "target": "Bandit" }

        - leave: if you do not wish to participate anymore
        Example: { "action": "leave" }


    Stay in character. 
    Only act from your own perspective. 
    Try to inject something new into the conversation.
    You may only do one action at a time.
    """

    def __init__(self, name, personality, goal, strength = 10, intelligence = 10, charisma = 10, luck = 10):
        super().__init__(name, personality, goal, strength, intelligence, charisma, luck)
        self.llm = LLM()

        # by default, uses its own LLM for context management, but in theory,
        # could use a different LLM for summarizing than for dialogue generation
        self.context = SummaryContext(self.name, self.personality, self.goal, self.llm)
        self.last_output = None

        self.wait_min = 10 - self.lck_mod - self.int_mod
        self.wait_max = self.wait_min + abs(self.lck_mod) + abs(self.int_mod)

        timestamp = datetime.now()
        self.logger = create_npc_logger(name, timestamp)

    def run(self):
        self.connect()
        
        quiet_round_passed = False

        # main loop
        while True:
            new_messages = False
            try:
                self.logger.info(f"{self.name} is checking for new messages")
                while self.conn.poll():
                    msg = self.conn.recv()

                    if msg["type"] == "context":
                        self.context.append(msg["content"])
                        new_messages = True
                    elif msg["type"] == "room":
                        self.room_info = msg["content"]

                    self.logger.info(f"{self.name} received world message: {msg}")

            except EOFError:
                break

            if new_messages or quiet_round_passed:
                prompt = [
                    {"role": "developer", "content": NPC.SYSTEM_MESSAGE + "\n" + self.character_sheet() + "\n" + self.context.summary}
                ] + self.context.context

                if self.context.context == []:
                    prompt.append(
                        {"role": "developer", "content": "No messages! Say hello!"}
                    )
                self.logger.info(f"{self.name} sending to LLM. Prompt:\n{prompt}")
                response = self.llm.prompt(prompt, json=True)
                output = response.output_text
                
                self.logger.info(f"{self.name} received LLM response:\n{response.output}")

                try:
                    output = json.loads(output)

                    if output == self.last_output and output["action"] != 'listen':
                        self.logger.warning(f"{self.name} is being repetitive.")
                    else:
                        self.context.append({"role": "assistant", "content": response.output_text})


                    if output["action"] == "leave":
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
                
                quiet_round_passed = False
            
            else:
                self.context.append({"role": "developer", "content": "It's quiet."})
                self.logger.info("Added quiet message to context.")
                quiet_round_passed = True

            # to keep things from going too fast
            time.sleep(random.randint(self.wait_min, self.wait_max)) 

        self.conn.close()
    
        
if __name__ == "__main__":

    mick = NPC("Mick", "stoic, speaks only when necessary", "keep order in your bar, keep outlaws out NO OUTLAWS, will attack if they don't leave voluntarily", charisma=13, luck=9)
    robin = NPC("Robin", "grumpy, but with a good heart", "fight your headache, relax after a long day of work in the mines, stay in your bar stool", charisma=10, luck=8)
    franklin = NPC("Franklin", "anxious, quick to leave", "start a new life, get a new job, hide the fact you have a bounty the next planet over", charisma=9, intelligence=12, luck=7)
    maverick = NPC("Deadeye", "bold, with a bit too quick a trigger finger", "hunt bounties, make money", charisma=12, intelligence=11, luck=13)
    bandit = NPC("Sandy", "aggressive, a little unhinged", "rob the saloon, be the first to shoot someone", charisma=11, intelligence=8, luck=15)

    try:
        mick.start()
        robin.start()
        time.sleep(random.randint(30,60))
        franklin.start()
        time.sleep(random.randint(60,120))
        bandit.start()
        time.sleep(random.randint(30,120))
        maverick.start()
    except ConnectionResetError as e:
        print("Server closed, all agents died.")