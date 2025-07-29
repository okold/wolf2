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
from colorama import Fore, Style

NPCS_PATH = "npcs.csv"

def resolve_majority_vote(votes: dict, tiebreaker = False) -> str | None:
    """
    Given a dictionary of votes {voter: target}, returns the target with majority.
    If there's no clear majority (tie or no votes), returns None.
    """

    if not votes:
        return None
    
    #self.log(votes)

    vote_counts = Counter(votes.values())
    most_common = vote_counts.most_common(2)

    # Check if there's a tie or no clear majority
    if len(most_common) == 1:
        return most_common[0][0]  # Only one person voted
    elif most_common[0][1] > most_common[1][1]:
        return most_common[0][0]  # Clear majority
    else:
        if tiebreaker:
            return random.choice([most_common[0][0], most_common[1][0]])
        return None

def normalize_role(role):
    """
    Normalizes funky roles to their main team.
    """
    return "villager" if role in ("seer", "villager") else role

class WolfWorld(World):

    NIGHT_PHASE_LENGTH = 60
    DAY_PHASE_LENGTH = 120
    NOTIFY_PERIOD = 30
    PLAYER_COUNT = 6
    NUM_WOLVES = 2
    PRINT_COOLDOWN = 3

    def __init__(self, cli: Connection = None):

        self.day_room = Room("Village Tavern", "The village's official meeting place.")
        self.night_room = Room("Hideout", "A cave on the outskirts of the village.")

        super().__init__(cli = cli, default_room=self.day_room)

        self.rooms[self.night_room.name] = self.night_room
        self.phase = "night"
        self.votes = {}
        self.valid_vote_targets = []

        self.current_room = self.night_room

    def check_winner(self):
        """
        Checks to see if any team has won.

        TODO: For now, just prints a victory message and terminates.

        Generated code: GPT 4o
        """
        roles = [normalize_role(actor["role"]) for actor in self.actors.values()]

        unique_roles = set(roles)

        if len(unique_roles) == 1:
            all_same_role = True
            role_value = unique_roles.pop()
        else:
            all_same_role = False
            role_value = None  # or list(unique_roles) if needed
        
        if all_same_role:
            self.log(f"Winning team: {role_value}")
            #self.kill()

    def vote(self, actor: str, target: str):
        if target in self.valid_vote_targets:
            self.votes[actor] = target
            self.send_to_room(self.actors[actor]["room"],
                            {"role": "system", "content": f"{actor} has voted for {target}! The current votes are: {self.votes}"})

        
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
            self.send_to_room(self.day_room.name, self.valid_vote_targets, "vote_targets", verbose=False)
        else:
            self.send_to_room(self.night_room.name, self.valid_vote_targets, "vote_targets", verbose = False)
        

    def run(self):
        self.connection_loop.start()
        self.print_loop.start()

        while True:
            with self.actors_lock:
                if len(self.actors) == self.PLAYER_COUNT:
                    self.accept_connections = False
                    break
            time.sleep(1) # TODO: variable here


        roles = ["werewolf"] * self.NUM_WOLVES + ["villager"] * (self.PLAYER_COUNT - self.NUM_WOLVES - 1) + ["seer"]
        random.shuffle(roles)

        for actor in self.actors:
            self.send_sleep_message(actor)

        seer_targets = {}

        for actor, role in zip(self.actors, roles):
            self.actors[actor]["role"] = role
            self.send_to_actor(actor, role, "role")
            #print(f"{actor} is a {role}.")

            if role != "seer":
                seer_targets[actor] = role

        phase_number = 1
        self.log(f"------------- {self.phase.upper()} {phase_number} ---")

        for actor in self.actors:
            if self.actors[actor]["role"] == "werewolf":
                self.move_actor_to_room(actor, self.night_room.name)

        self.reset_votes()
        self.send_to_room(self.night_room.name, {"role": "system", "content": "This is the first night. You werewolves have met to plot your first kill."})
        self.awaken_room(self.night_room.name)            

        
        phase_start_time = time.time()
        last_notify = phase_start_time
        phase_duration = self.NIGHT_PHASE_LENGTH

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

                actor = self.actors[msg["actor"]]

                if actor["role"] == "werewolf":
                    colour = Fore.RED
                elif actor["role"] == "seer":
                    colour = Fore.CYAN
                else:
                    colour = Fore.YELLOW

                if msg["room"] == self.current_room.name:
                    if msg["action"] == "speak" and actor["can_speak"]:
                        speak_contest.add_speaker(msg["actor"], msg["content"], actor["charisma"], msg["room"], colour)
                    if "speech" in msg and msg["action"] != "speak" and actor["can_speak"]:
                        speak_contest.add_speaker(msg["actor"], msg["speech"], actor["charisma"], msg["room"], colour)
                    if msg["action"] == "yell":
                        self.yell(msg["actor"], msg["content"])
                    if msg["action"] == "gesture":
                        self.gesture(msg["actor"], msg["content"])
                    if "gesture" in msg and msg["action"] != "gesture":
                        self.gesture(msg["actor"], msg["gesture"])
                    if msg["action"] == "vote":
                        self.vote(msg["actor"], msg["target"])

            speak_output_plain, speak_output_colour, speak_actor, interrupted_actors = speak_contest.resolve()

            if speak_output_plain and speak_contest.room == self.current_room.name:
                room = self.actors[speak_actor]["room"]
                self.send_to_room(room, speak_output_plain, verbose=False)
                self.log(speak_output_colour)
                for actor in interrupted_actors:
                    self.send_to_room(room, {"role": "user", "content": f"{actor} was interrupted by {speak_actor}!"}, verbose=False)

            elapsed = int(time.time() - phase_start_time)

            if elapsed >= phase_duration:
                vote_result = resolve_majority_vote(self.votes, tiebreaker=True)
            else:
                vote_result = resolve_majority_vote(self.votes)

            if elapsed < phase_duration:
                if time.time() - last_notify >= self.NOTIFY_PERIOD:
                    message = f"There are {phase_duration - elapsed} seconds remaining in the phase!"
                    self.send_to_room(self.current_room.name, {"role": "system", "content": message})
                    last_notify = time.time()

            if vote_result or elapsed >= phase_duration:
                if vote_result:
                    self.remove(vote_result, "killed")
                    if vote_result in seer_targets: 
                        del seer_targets[vote_result]
                    self.send_to_room(self.current_room.name, {"role": "system", "content": f"{vote_result} has been killed! Role: {self.actors[vote_result]['role']}."})

                if self.phase == "night":
                    self.phase = "day"
                    self.current_room = self.day_room
                    
                else:
                    self.phase = "night"
                    phase_number += 1
                    self.current_room = self.night_room

                self.clean_flagged_actors(verbose=False)
                #self.check_winner()

                self.log(f"------------- {self.phase.upper()} {phase_number} ---")
                self.send_to_room(self.current_room.name, {"role": "system", "content": f"It is now the {self.phase} phase!"}, verbose=False)

                wolf_count = sum(1 for actor in self.actors if self.actors[actor]["role"] == "werewolf")
                villager_count = sum(1 for actor in self.actors if self.actors[actor]["role"] == "villager" or self.actors[actor]["role"] == "seer")

                if vote_result:
                    day_message = f"You have met at the village tavern, to discuss {vote_result}'s death. {wolf_count} werewolves remain. {villager_count} villagers remain."
                else:
                    day_message = f"You have met at the village tavern. The night was quiet. {wolf_count} werewolves remain. {villager_count} villagers remain."
                
                if wolf_count == 1:
                    night_message = f"You are the last remaining werewolf. Plan your next kill! {villager_count} villagers remain."
                else:
                    night_message = f"You are meeting at the werewolf hideout. Plan your next kill! {villager_count} villagers remain."

                if self.phase == "day":
                    self.log(day_message)
                else:
                    self.log(night_message)

                for actor in self.actors:
                    try:
                        self.send_sleep_message(actor)
                        self.send_phase_message(actor, self.phase)
                        role = self.actors[actor]["role"]

                        if self.phase == "day":
                            self.move_actor_to_room(actor, self.day_room.name, verbose=False)
                            self.send_to_actor(actor, {"role": "system", "content": day_message})
                            phase_duration = self.DAY_PHASE_LENGTH

                            if self.actors[actor]["role"] == "seer":
                                target = random.choice(list(seer_targets.keys()))
                                self.send_to_actor(actor, {"role": "system", "content": f"Last night, you receieved a vision! {target} is a {seer_targets[target]}!"})
                                self.log(f"{actor} recieved {target}'s role: {seer_targets[target]}")
                                del seer_targets[target]
                            elif role == "villager":
                                self.send_to_actor(actor, "You were sleeping last night, though perhaps not very well.")

                        elif self.phase == "night" and self.actors[actor]["role"] == "werewolf":
                            self.move_actor_to_room(actor, self.night_room.name, verbose = False)
                            
                            self.send_to_actor(actor, {"role": "system", "content": night_message})
                            phase_duration = self.NIGHT_PHASE_LENGTH
                    except Exception as e:
                        self.logger.exception(e)

                self.reset_votes()
                self.awaken_room(self.current_room.name)

                phase_start_time = time.time()
                last_notify = phase_start_time

            
            self.clean_flagged_actors()
            #self.check_winner()  

            time.sleep(self.WAIT_TIME)



class WolfNPC(NPC):

    def __init__(self, name, personality, goal, description, can_speak, gender):
        super().__init__(name, personality, goal, description, can_speak, gender)

        with open('game/npc_system_message.txt', 'r', encoding='utf-8') as file:
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
        Make note of other players and their suspected roles.
        If you are the seer, remember your visions.
        If you are a werewolf, remember who your allies are.
        """
        return super().update_summary_message(new_message)

if __name__ == "__main__":

    player_list = []

    with open(NPCS_PATH, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        npc_list = [row for _, row in zip(range(WolfWorld.PLAYER_COUNT), reader)]

    # create and start server
    parent_conn, child_conn = Pipe()
    world = WolfWorld(child_conn)
    world.start()

    world.log("Spawning bots...")
    for npc in npc_list:
        #self.log(npc)
        
        if npc["can_speak"].upper() == "TRUE":
            npc["can_speak"] = True
        else:
            npc["can_speak"] = False

        bot_player= WolfNPC(npc["name"], npc["personality"], npc["goal"], npc["description"], npc["can_speak"], npc["gender"])
        bot_player.start()
        player_list.append(bot_player)

        #time.sleep(random.randint(5,60))



    world.log("Done spawning bots, CLI free.")


    while True:
        msg = input()
        parent_conn.send(msg)
        if msg == "quit" or msg == "exit":
            break

