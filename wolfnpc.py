import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from npc import NPC

class WolfNPC(NPC):

    def __init__(self, name, personality, goal, description, can_speak, gender, llm=None, turn_based = True, sys_message_file = "npc_system_message_turn_based.txt"):
        super().__init__(name, personality, goal, description, can_speak, gender, llm, turn_based)

        with open(f'game/{sys_message_file}', 'r', encoding='utf-8') as file:
            self.SYSTEM_MESSAGE = file.read()

    def character_sheet(self) -> str:
        """
        Returns a character sheet, for use in LLM contexts.
        """

        desc = f"""YOUR CHARACTER SHEET:
        Name: {self.name}
        Role: {self.role}
        Personality: {self.personality}
        Description: {self.description}

        You are currently in a room named: {self.room_info['name']}
        {self.room_info['description']}
        
        """

        desc += f"""Valid vote targets are:
        {self.vote_targets}
        ---
        """

        return desc
    
    def update_summary_message(self):
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