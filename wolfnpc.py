import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from npc import NPC

class WolfNPC(NPC):

    WOLF_DAY = "Pretend to be an innocent villager. Do not put suspicion on your teammates. If the seer lives, try to deduce their identity and convince the village to lynch them."
    WOLF_NIGHT = "Team up with the others in the hideout to plan the village's extermination."
    SEER_STRAT = "If you receive a vision of a werewolf, try to convince the village to lynch them."
    VILLAGE_STRAT = "Deduce who the werewolf(s) are to lynch them. If the seer lives and you trust them, use their vision to help guide the vote. Make note of anyone suspicious."

    def __init__(self, name, personality, goal, description, can_speak, gender, llm=None, turn_based = True, sys_message_file = "npc_system_message_turn_based.txt", logger=None, csv_logger = None, strategy="summary"):
        super().__init__(name, personality, goal, description, can_speak, gender, llm, turn_based, logger, csv_logger, strategy)

        with open(f'game/{sys_message_file}', 'r', encoding='utf-8') as file:
            self.SYSTEM_MESSAGE = file.read()

    def character_sheet(self) -> str:
        """
        Returns a character sheet, for use in LLM contexts.
        """

        if self.role == "werewolf":
            goal = "kill all the villagers"
        elif self.role in ["seer", "villager"]:
            goal = "survive, lynch all werewolves"

        if self.role == "werewolf" and self.phase == "day":
            strategy = self.WOLF_DAY
        elif self.role == "werewolf":
            strategy = self.WOLF_NIGHT
        elif self.role == "seer":
            strategy = self.SEER_STRAT
        else:
            strategy = self.VILLAGE_STRAT

        desc = f"""CHARACTER SHEET:
Name: {self.name}
Role: {self.role}
Personality: {self.personality}
Description: {self.description}
Goal: {goal}

Current Phase: {self.phase}

You are currently in a room named: {self.room_info['name']}
{self.room_info['description']}

People in the room are:
{self.room_info['actors']}

Valid vote targets are:
{self.vote_targets}

General strategy:
{strategy}

"""
        return desc
    
    def gen_system_prompt(self):

        if self.strategy == "summary":
            prompt = [
                {"role": "system", "content": self.SYSTEM_MESSAGE + self.character_sheet() + "\nCurrent Summary:\n" + self.context.summary}
            ] + self.context.context
        else:
            prompt = [
                {"role": "system", "content": self.SYSTEM_MESSAGE + self.character_sheet()}
            ] + self.context.context

        #prompt.append({"role": "system", "content": self.character_sheet()})

        prompt.append({"role": "system", "content": f"Stay in character as {self.name}, the {self.role}."})

        return prompt

    def update_role(self, new_role):
        if new_role == "werewolf":
            self.goal = "wipe out the village"
        else:
            self.goal = "survive the werewolf attacks"

        return super().update_role(new_role)
        

    def generate_summary_message(self):

        if self.role == "seer":
            role_message = "\nAs the seer, remember your visions."
        if self.role == "werewolf":
            role_message = "\nAs a werewolf, remember who your teammate is."
        else:
            role_message = ""

        new_message = f"""You are an actor in a game of werewolf.

{self.character_sheet()}

Summarize the following log in plain English, in first person.
Update your previous summary.
Make a list of other players and what roles you suspect or know they have.
Write your strategy for the next day of the game.
{role_message}

PREVIOUS SUMMARY:
{self.context.summary}
"""
        return new_message