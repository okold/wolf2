import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from npc import NPC

class WolfNPC(NPC):

    WOLF_DAY = "Pretend to be an innocent villager. Do not put suspicion on your teammates. If the seer lives, try to deduce their identity and convince the village to lynch them."
    WOLF_NIGHT = "Plan your daytime strategy. If the seer lives, try to deduce their identity and kill them."
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

        desc = f"""CHARACTER SHEET:
Your Name: {self.name}
Your Role: {self.role}
Your Personality: {self.personality}
Your Description: {self.description}

You are currently in a room named: {self.room_info['name']}
{self.room_info['description']}
        
"""

        desc += f"""Valid vote targets are:
{self.vote_targets}
        

"""


        if self.role == "werewolf" and self.phase == "day":
            strategy = self.WOLF_DAY
        elif self.role == "werewolf":
            strategy = self.WOLF_NIGHT
        elif self.role == "seer":
            strategy = self.SEER_STRAT
        else:
            strategy = self.VILLAGE_STRAT

        desc += f"""General strategy:
{strategy}
"""

        return desc
    
    def gen_system_prompt(self):

        if self.strategy == "summary":
            prompt = [
                {"role": "system", "content": self.SYSTEM_MESSAGE + "\nCurrent Summary:\n" + self.context.summary}
            ] + self.context.context
        else:
            prompt = [
                {"role": "system", "content": self.SYSTEM_MESSAGE}
            ] + self.context.context

        prompt.append({"role": "system", "content": self.character_sheet()})

        prompt.append({"role": "system", "content": f"Remember your identity as {self.name}, the {self.role}. All other players are strangers to you."})

        return prompt

    def update_summary_message(self):
        new_message = f"""You are playing a game of werewolf, and your role is: {self.role}.
        Summarize all known knowledge. Be detailed. Keep your summary in first person.
        Make a list of other players and what roles you suspect they have.
        Remember what you were doing in previous rounds, if applicable.
        Write your strategy moving forward.
        """

        if self.role == "seer":
            new_message += "\nAs the seer, remember your visions."
        if self.role == "werewolf":
            new_message += "\nAs a werewolf, remember who your teammate is."
        
        return super().update_summary_message(new_message)