from actor import Actor
from context import SummaryContext, WindowContext
from llm import LLM, BasicActionMessage, AdvancedActionMessage
from abc import ABC, abstractmethod
import time
import random
import json
from utils import create_logger
from datetime import datetime
from room import Room
from logging import Logger

#SUMMARY_MODEL = "gpt-oss:20b"
SUMMARY_MODEL = "llama4:16x17b"
#SUMMARY_MODEL = "mistral-small3.2"
#SUMMARY_MODEL = "llama3.1:70b"

class NPC(Actor, ABC):

    WAIT_MIN = 3
    WAIT_MAX = 8

    def __init__(self, name, personality, goal, description, can_speak, gender, llm=None, turn_based=False, logger=None, csv_logger=None, strategy="window"):
        super().__init__(name, personality, goal, description, can_speak=can_speak, gender=gender)
        if not llm:
            self.llm = LLM()
        else:
            self.llm = llm

        # by default, uses its own LLM for context management, but in theory,
        # could use a different LLM for summarizing than for dialogue generation
        self.logger = logger
        self.csv_logger = csv_logger

        self.context = None
        self.set_strategy(strategy)
        self.last_output = None
        
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

    def set_strategy(self, strategy):
        self.strategy = strategy

        if self.strategy == "summary":
            if self.context != None:
                memory = self.context.context
                last_summary = self.context.summary
            else:
                memory = []
                last_summary = "Your memories are fresh!"
            summary_llm = LLM(False, SUMMARY_MODEL)
            self.context = SummaryContext(self.name, 
                                          self.personality, 
                                          self.goal, 
                                          summary_llm, 
                                          logger=self.logger, 
                                          csv_logger=self.csv_logger, 
                                          context=memory, 
                                          summary=last_summary)
        else:
            self.context = WindowContext()


    def update_system_message(self):
        self.system_message = self.system_message

    @abstractmethod
    def generate_summary_message(self) -> str:
        return ""

    def summarize(self):
        if self.strategy == "summary":
            self.context.summarize(self.generate_summary_message())
    
    @abstractmethod
    def gen_system_prompt(self):

        if self.strategy == "summary":
            prompt = [
                {"role": "system", "content": self.SYSTEM_MESSAGE + "\n" + self.character_sheet() + "\nCurrent Summary:\n" + self.context.summary}
            ] + self.context.context
        else:
            prompt = [
                {"role": "system", "content": self.SYSTEM_MESSAGE + "\n" + self.character_sheet() + "\nGeneral Strategy:\n"}
            ] + self.context.context

        return prompt

    def act(self):

        prompt = self.gen_system_prompt()

        if isinstance(self.logger, Logger):
            self.logger.info(f"{self.name} sending to LLM. Prompt:\n{prompt}")

        content, reasoning, tokens_in, tokens_out, eval_in, eval_out = self.llm.prompt(prompt, enforce_model=self.action_model)
        
        if isinstance(self.logger, Logger):
            self.logger.info(f"{self.name} received response from {self.llm.model}. Tokens in: {tokens_in} ({eval_in} ms), tokens out: {tokens_out} ({eval_out} ms)\n{reasoning}\n{content}")
        
        output_str = content

        try:

            output = json.loads(output_str)

            self.csv_logger.log(actor=self.name, action="prompt", content=output_str, tokens_in=tokens_in, tokens_out=tokens_out, eval_in=eval_in, eval_out=eval_out, model=self.llm.model, prompt=prompt, context_length=len(self.context.context), strategy=self.strategy, role=self.role, phase=self.phase)

            if output_str == self.last_output:
                self.csv_logger.log(actor=self.name, content="WARNING: suppresesd duplicate message")
                self.conn.send({"action": "vote", "content": "self"})
            else:
                self.last_output = output_str

            self.context.append({"role": "assistant", "content": output_str})

            if isinstance(self.logger, Logger):
                self.logger.info(f"{self.name} sent to world: {output}")
            self.conn.send(output)

        except Exception as e:
            self.conn.send({"action": "vote", "content": f"{self.name}", "reason": f"Exception: {e}"})
            
    def update_role(self, new_role):
        self.role = new_role

    def run(self):
        self.connect()
        
        quiet_round_passed = False

        # main loop
        while True:
            self.new_messages = False
            try:
                while self.conn.poll():
                    msg = self.conn.recv()

                    if isinstance(self.logger, Logger):
                        self.logger.info(f"{self.name} received world message: {msg}")
                    
                    if msg["type"] == "context":
                        self.context.append(msg["content"])
                        self.new_messages = True
                    elif msg["type"] == "summarize":
                        self.summarize()
                        self.conn.send({"action": "ready"})
                    elif msg["type"] == "room":
                        self.room_info = msg["content"]
                    elif msg["type"] == "role":
                        self.update_role(msg["content"])
                    elif msg["type"] == "sleep":
                        self.is_awake = False
                    elif msg["type"] == "wake":
                        self.is_awake = True
                    elif msg["type"] == "phase":
                        self.phase = msg["content"]
                    elif msg["type"] == "vote_targets":
                        self.vote_targets = msg["content"]
                    elif msg["type"] == "act_token":
                        self.has_turn = True
                    elif msg["type"] == "strategy":
                        self.set_strategy(msg["content"])

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