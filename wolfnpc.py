from multiprocessing.connection import Listener, Pipe, Connection
from collections import Counter
import random
import time
import sys
import math
import os
import csv

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from npc import NPC
from world import World
from room import Room
from llm import LLM
from speech import SpeakingContest
from colorama import Fore, Style

class WolfNPC(NPC):

    def __init__(self, name, personality, goal, description, can_speak, gender, llm=None, turn_based = False, sys_message_file = "npc_system_message"):
        super().__init__(name, personality, goal, description, can_speak, gender, llm, turn_based)

        with open(f'game/{sys_message_file}.txt', 'r', encoding='utf-8') as file:
            self.SYSTEM_MESSAGE = file.read()

    def character_sheet(self) -> str:
        """
        Returns a character sheet, for use in LLM contexts.
        """

        desc = f"""--CHARACTER SHEET--
        Your name: {self.name}
        Your role is: {self.role}
        Game phase: {self.phase}
        Your personality: {self.personality}
        Your gender: {self.gender}
        Your speech capability: {self.can_speak}

        You are currently in a room named: {self.room_info['name']}
        {self.room_info['description']}
        
        The actors in the room are:
        """

        for actor in self.room_info["actors"]:
            desc += f" {actor}: {self.description} ({self.room_info['actors'][actor]['status']})"

        desc += f"""Valid vote targets are:
        {self.vote_targets}
        ---
        """

        return desc
    
    def update_summary_message(self, new_message : str):
        new_message = f"""Update your long-term memory by summarizing and integrating your short-term memory.
        Keep your summary in first person.
        You are playing a game of werewolf, and your role is: {self.role}.
        The current phase of the game is: {self.phase}
        Make note of other players and what roles you suspect they have.
        Remember what you were doing the previous night.
        """

        if self.role == "seer":
            new_message += "\nAs the seer, remember your visions."
        if self.role == "werewolf":
            new_message += "\nAs a werewolf, remember who your teammate is."
        
        return super().update_summary_message(new_message)