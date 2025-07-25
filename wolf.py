from multiprocessing.connection import Listener, Pipe, Connection
from collections import Counter
import random
import time
import sys
import os
import csv

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from npc import NPC
from world import World
from room import Room
from llm import LLM
from speech import SpeakingContest

NPCS_PATH = "npcs.csv"


def resolve_majority_vote(votes: dict) -> str | None:
    """
    Given a dictionary of votes {voter: target}, returns the target with majority.
    If there's no clear majority (tie or no votes), returns None.
    """
    if not votes:
        return None
    
    #print(votes)

    vote_counts = Counter(votes.values())
    most_common = vote_counts.most_common(2)

    # Check if there's a tie or no clear majority
    if len(most_common) == 1:
        return most_common[0][0]  # Only one person voted
    elif most_common[0][1] > most_common[1][1]:
        return most_common[0][0]  # Clear majority
    else:
        return None  # Tie

class WolfWorld(World):

    PLAYER_COUNT = 6
    NUM_WOLVES = 2

    def __init__(self, cli: Connection = None):

        self.day_room = Room("Village Tavern", "The village's official meeting place.")
        self.night_room = Room("Hideout", "A cave on the outskirts of the village.")

        super().__init__(cli = cli, default_room=self.day_room)

        self.rooms[self.night_room.name] = self.night_room
        self.phase = "night"
        self.votes = {}
        self.valid_vote_targets = []

        self.current_room = self.night_room

    def vote(self, actor: str, target: str):
        self.send_to_room(self.actors[actor]["room"],
                          {"role": "system", "content": f"{actor} has voted for {target}!"})
        if target in self.valid_vote_targets:
            self.votes[actor] = target

        

        
    def reset_votes(self):
        self.valid_vote_targets = []
        self.votes = {}

        with self.actors_lock:
            for actor in self.actors:
                if self.actors[actor]["status"] == "alive":
                    if self.phase == "day":
                        self.valid_vote_targets.append(actor)
                        self.votes[actor] = None
                    elif self.phase == "night" and self.actors[actor]["role"] == "villager":
                        self.valid_vote_targets.append(actor)
                    elif self.phase == "night" and  self.actors[actor]["role"] == "werewolf":
                        self.votes[actor] = None
        
        if self.phase == "day":
            self.send_to_room(self.day_room.name, self.valid_vote_targets, "vote_targets")
        else:
            self.send_to_room(self.night_room.name, self.valid_vote_targets, "vote_targets")
        

    def run(self):
        self.connection_loop.start()

        while True:
            with self.actors_lock:
                if len(self.actors) == self.PLAYER_COUNT:
                    self.accept_connections = False
                    break
            time.sleep(1) # TODO: variable here


        roles = ["werewolf"] * 2 + ["villager"] * 4
        random.shuffle(roles)

        for actor in self.actors:
            self.send_sleep_message(actor)

        for actor, role in zip(self.actors, roles):
            self.actors[actor]["role"] = role
            self.send_to_actor(actor, role, "role")

            if role == "werewolf":
                self.move_actor_to_room(actor, self.night_room.name)

        self.reset_votes()
        self.awaken_room(self.night_room.name)            

        # main loop
        while True:

            # logic for who gets to successfully speak this round
            speak_contest = SpeakingContest(self.current_room.name)



            # check for cli messages
            msg = self.try_recv(self.cli)
            if msg == "quit" or msg == "exit":
                break

            new_messages = self.get_new_messages()

            for msg in new_messages:
                if msg["room"] == self.current_room.name:
                    if msg["action"] == "speak" and self.actors[msg["actor"]]["can_speak"]:
                        speak_contest.add_speaker(msg["actor"], msg["content"], self.actors[msg["actor"]]["charisma"], msg["room"])
                    if "comment" in msg and msg["action"] != "speak" and self.actors[msg["actor"]]["can_speak"]:
                        speak_contest.add_speaker(msg["actor"], msg["comment"], self.actors[msg["actor"]]["charisma"], msg["room"])
                    if msg["action"] == "yell":
                        self.yell(msg["actor"], msg["content"])
                    if msg["action"] == "gesture":
                        self.gesture(msg["actor"], msg["content"])
                    if "gesture" in msg and msg["action"] != "gesture":
                        self.gesture(msg["actor"], msg["gesture"])
                    if msg["action"] == "vote":
                        self.vote(msg["actor"], msg["target"])
                        self.print_info(self.votes)

            speak_output, speak_actor, interrupted_actors = speak_contest.resolve()

            if speak_output and speak_contest.room == self.current_room.name:
                room = self.actors[speak_actor]["room"]
                self.send_to_room(room, speak_output)
                #for actor in interrupted_actors:
                #    self.send_to_room(self.actors[speak_actor]["room"], {"role": "user", "content": f"{actor} was interrupted by {speak_actor}!"})

            vote_result = resolve_majority_vote(self.votes)

            if vote_result:
                self.remove(vote_result, "killed")
                self.send_to_room(self.current_room.name, {"role": "system", "content": f"{vote_result} has been killed! Role: {self.actors[vote_result]['role']}."})

                if self.phase == "night":
                    self.phase = "day"
                    self.current_room = self.day_room
                    
                else:
                    self.phase = "night"
                    self.current_room = self.night_room
                    self.print_info("Moved to Night phase!")

                self.send_to_room(self.current_room.name, f"It is now the {self.phase} phase!")

                for actor in self.actors:
                    if self.actors[actor]["status"] == "alive":
                        try:
                            self.send_sleep_message(actor)
                            self.send_phase_message(actor, self.phase)
                            self.send_summary_message(actor)

                            if self.phase == "day":
                                self.move_actor_to_room(actor, self.day_room.name)
                            elif self.phase == "night" and self.actors[actor]["role"] == "werewolf":
                                self.move_actor_to_room(actor, self.night_room.name)
                        except Exception as e:
                            self.logger.exception(e)
                    
                self.reset_votes()
                self.awaken_room(self.current_room.name)

            
            self.clean_flagged_actors()    

            time.sleep(World.WAIT_TIME)



class WolfNPC(NPC):

    SYSTEM_MESSAGE_GEN = """You are an actor in a game of Werewolf. Stay in character and try to win according to your role.

PHASES:
- NIGHT (2 min or until vote passes): Only werewolves act. They vote on a target to kill.
- DAY (5 min or until vote passes): All players act. Everyone votes on someone to lynch.
At the end of each phase, the killed player's role is revealed.

ROLES:
- WEREWOLF: Coordinate quietly at night. Blend in during the day. Don't reveal your role. Push suspicion subtly.
- VILLAGER: Use conversation to identify and vote out werewolves. Trust cautiously.

VICTORY:
- Werewolves win if all villagers are dead.
- Villagers win if all werewolves are dead.

Your output must be valid JSON with ONE action per message.
Examples:
{ "action": "speak", "content": "I don’t trust Elda." }
{ "action": "gesture", "content": "shrugs", "comment": "Could be anyone." }
{ "action": "vote", "target": "Boof" }
{ "action": "listen" }

Available actions: speak, gesture, yell, listen, vote.

Only act from your perspective. Don’t repeat yourself. Move the conversation forward."""

    SYSTEM_MESSAGE = """You are an actor in a game of Werewolf. The rules of the game are:
        - During the night phase, only werewolf players are active.
        The night phase lasts for two minutes, or until a vote has passed.

        - During the day phase, every player votes on who to lynch.
        The day phase lasts for five minutes, or until a vote has passed.
        
    At the end of the current phase, the role of the killed player is revealed.

    The werewolves win if all villagers have been killed.
    The villagers win if the werewolves have been killed.

    Your output must be valid JSON. 
    Example: { "action": <action_name>, "content": <varies_by_action>, "target": <name>, "comment": <additional_dialogue> }

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

        - vote: vote on a player to kill (night) or lynch (day)
        Example: { "action": "vote", "target": "Bandit" }

    Stay in character. 
    Only act from your own perspective. 
    Try to inject something new into the conversation.
    You may only do one action at a time.
    """

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
        Your speech Capability: {self.can_speak}

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
        Remember your allies and keep in mind any strategies for proceeding.
        """
        return super().update_summary_message(new_message)

if __name__ == "__main__":


    player_list = []

    with open(NPCS_PATH, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        npc_list = [row for row in reader]

    # create and start server
    parent_conn, child_conn = Pipe()
    world = WolfWorld(child_conn)
    world.start()

    print("Spawning bots...")
    for npc in npc_list:
        #print(npc)
        
        if npc["can_speak"].upper() == "TRUE":
            npc["can_speak"] = True
        else:
            npc["can_speak"] = False

        bot_player= WolfNPC(npc["name"], npc["personality"], npc["goal"], npc["description"], npc["can_speak"], npc["gender"])
        bot_player.start()
        player_list.append(bot_player)

        #time.sleep(random.randint(5,60))



    print("Done spawning bots, CLI free.")


    while True:
        msg = input()
        parent_conn.send(msg)
        if msg == "quit" or msg == "exit":
            break

    for bot in player_list:
        bot.kill()


