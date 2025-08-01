from actor import Actor
from context import SummaryContext
from llm import LLM, BasicActionMessage, AdvancedActionMessage
from abc import ABC, abstractmethod
import time
import random
import json
from utils import create_logger
from datetime import datetime
from room import Room

class NPC(Actor, ABC):

    WAIT_MIN = 3
    WAIT_MAX = 8

    def __init__(self, name, personality, goal, description, can_speak, gender, llm=None, turn_based=False):
        super().__init__(name, personality, goal, description, can_speak=can_speak, gender=gender)
        if not llm:
            self.llm = LLM()
        else:
            self.llm = llm

        # by default, uses its own LLM for context management, but in theory,
        # could use a different LLM for summarizing than for dialogue generation
        self.logger = create_logger(name)
        self.context = SummaryContext(self.name, self.personality, self.goal, self.llm, logger=self.logger)
        self.last_output = None

        self.wait_min = max(0, 10 - self.lck_mod - self.int_mod - 1)
        self.wait_max = min(20, self.wait_min + abs(self.lck_mod) + abs(self.int_mod) + 1)



        
        self.turn_based = turn_based

        if turn_based:
            self.action_model = BasicActionMessage
        else:
            self.action_model = AdvancedActionMessage

        self.has_turn = False

        # REALTIME THINGS
        self.is_awake = False   # start npcs asleep
        self.new_messages = False # used in real-time processing


    def update_system_message(self):
        self.system_message = self.system_message

    @abstractmethod
    def update_summary_message(self):
        pass

    def summarize(self):
        self.update_summary_message()
        self.context.summarize()

    def act(self):
        prompt = [
            {"role": "system", "content": self.SYSTEM_MESSAGE + "\n" + self.character_sheet() + "\nCurrent Summary:\n" + self.context.summary}
        ] + self.context.context

        self.logger.info(f"{self.name} sending to LLM. Prompt:\n{prompt}")
        content, reasoning, usage = self.llm.prompt(prompt, enforce_model=self.action_model)
        
        self.logger.info(f"{self.name} received response from {self.llm.model}. Usage: {usage}\n{reasoning}\n{content}")
        output_str = content
        tried_fix = False

        while True:
            try:
                output = json.loads(output_str)

                #if isinstance(output, dict):
                    #self.context.append({"role": "assistant", "content": output_str})

                self.logger.info(f"{self.name} sent to world: {output}")
                self.conn.send(output)
                break

            except Exception as e:
                if tried_fix:
                    self.logger.warning(f"Failed to parse LLM output: {e}")
                    self.logger.warning(f"Offending output:\n{output_str}")
                    self.conn.send({"vote": None, "speech": None})  # Graceful fallback
                    break
                else:
                    output_str = output_str[2:]
                    tried_fix = True





    def run(self):
        self.connect()
        
        quiet_round_passed = False

        # main loop
        while True:
            self.new_messages = False
            try:
                while self.conn.poll():
                    msg = self.conn.recv()

                    self.logger.info(f"{self.name} received world message: {msg}")
                    
                    if msg["type"] == "context":
                        self.context.append(msg["content"])
                        self.new_messages = True
                    elif msg["type"] == "summarize":
                        self.context.summarize()
                        self.logger.info(f"Forced a summary!")
                    elif msg["type"] == "room":
                        self.room_info = msg["content"]
                        self.logger.info(f"Updated room info!")
                    elif msg["type"] == "role":
                        self.role = msg["content"]
                        self.logger.info(f"Received role: {self.role}")
                    elif msg["type"] == "sleep":
                        self.is_awake = False
                        self.logger.info(f"Put to sleep!")
                    elif msg["type"] == "wake":
                        self.is_awake = True
                        self.logger.info(f"Woken up!")
                    elif msg["type"] == "phase":
                        self.phase = msg["content"]
                        self.logger.info(f"Phase set to: {msg['content']}")
                    elif msg["type"] == "vote_targets":
                        self.vote_targets = msg["content"]
                        self.logger.info(f"Received vote targets: {self.vote_targets}")
                    elif msg["type"] == "act_token":
                        self.has_turn = True
                        self.logger.info(f"Recieved act token!")

                if not self.turn_based and self.is_awake and (quiet_round_passed or self.new_messages):
                    self.act()
                    self.new_messages = False
                    quiet_round_passed = False
                elif not self.turn_based:
                    quiet_round_passed = True

                if self.turn_based and self.has_turn:
                    self.act()
                    self.has_turn = False

            except EOFError:
                break
            except ConnectionResetError:
                break

            time.sleep(random.randint(self.WAIT_MIN, self.WAIT_MAX)) 

        try:
            self.conn.close()
        except:
             pass