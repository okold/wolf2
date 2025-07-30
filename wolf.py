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

NPCS_PATH = "npcs.csv"

def resolve_majority_vote(voters: dict, tiebreaker = False) -> str | None:
    """
    Given a dictionary of votes {voter: target}, returns the target with majority.
    If there's no clear majority (tie or no votes), returns None.
    """

    if not voters:
        return None
    
    if len(voters) == 1:
        for actor in voters:
            return voters[actor]
    
    #self.log(votes)

    vote_counts = Counter(voters.values())
    most_common = vote_counts.most_common(2)

    # Check if there's a tie or no clear majority
    if len(most_common) == 1:
        return most_common[0][0]  # Only one person voted
    elif most_common[0][1] > most_common[1][1]:
        return most_common[0][0]  # Clear majority
    elif tiebreaker:
        if most_common[0][0] == None:
            return most_common[1][0]
        elif most_common[1][0] == None:
            return most_common[0][0]
        else:
            return random.choice([most_common[0][0], most_common[1][0]])
    else:
        return None

def role_colour(role: str):
    if role == "werewolf":
        return Fore.RED
    elif role == "seer":
        return Fore.CYAN
    else:
        return Fore.YELLOW

def normalize_role(role):
    """
    Normalizes funky roles to their main team.
    """
    return "villager" if role in ("seer", "villager") else role

class WolfWorld(World):

    NIGHT_PHASE_LENGTH = 60
    DAY_PHASE_LENGTH = 120
    NOTIFY_PERIOD = 20
    PLAYER_COUNT = 6
    NUM_WOLVES = 2
    PRINT_COOLDOWN = 3

    def __init__(self, cli: Connection = None):

        self.day_room = Room("Village Tavern", "The village's official meeting place.")
        self.night_room = Room("Hideout", "A cave on the outskirts of the village.")

        # note to self: I init to the day room because then the villagers don't
        # start in the hideout... haha
        super().__init__(cli = cli, default_room=self.day_room)

        self.rooms[self.night_room.name] = self.night_room
        self.current_room = self.night_room
        self.phase = "night"
        self.phase_number = 1
        self.voters = {}
        self.seer_targets = {}
        self.valid_vote_targets = []    
        self.end = False  

    def print_loop(self):
        """
        Limits prints to one every PRINT_COOLDOWN seconds.
        """
        while True:
            try:
                if self.print_queue.empty() and self.end:
                    break
                else:
                    message = self.print_queue.get()

                    if isinstance(message, dict):
                        try:
                            if message["role"] == "user":
                                message = message["content"]
                            elif message["role"] == "system":
                                message = f"\033[1mSYSTEM:\033[0m {message['content']}"
                        except:
                            pass

                    print(message)

            except Exception as e:
                self.logger.warning(e)
            time.sleep(self.PRINT_COOLDOWN)

    def vote(self, actor: str, target: str):
        if target in self.valid_vote_targets:
            self.voters[actor] = target
            message = f"{actor} has voted for {target}! The current votes are:"
            
            for voter in self.voters:
                if self.voters[voter] != None:
                    message += f"\n\t{voter}: {self.voters[voter]}"
            
            if self.phase == "day":
                message += f"\n\tVotes needed to lynch: {math.ceil(len(self.actors)/2)}"

            self.send_to_room(self.actors[actor]["room"],
                            {"role": "system", "content": message})

        
    def reset_votes(self):
        self.valid_vote_targets = []
        self.voters = {}

        with self.actors_lock:
            for actor in self.actors:
                role = self.actors[actor]["role"]

                if self.actors[actor]["status"] == "alive":
                    if self.phase == "day":
                        self.valid_vote_targets.append(actor)
                        self.voters[actor] = None
                    elif self.phase == "night" and role in ["villager", "seer"]:
                        self.valid_vote_targets.append(actor)
                    elif self.phase == "night" and  role == "werewolf":
                        self.voters[actor] = None
        
        if self.phase == "day":
            self.send_to_room(self.day_room.name, self.valid_vote_targets, "vote_targets", verbose=False)
        else:
            self.send_to_room(self.night_room.name, self.valid_vote_targets, "vote_targets", verbose = False)
        
    def phase_header(self):
        self.log(f"-------------\033[1m{self.phase.upper()} {self.phase_number}: {self.current_room.name.upper()}\033[0m---\n{self.current_room.description}")

    def get_wolf_count(self) -> int:
        return sum(1 for actor in self.actors if self.actors[actor]["role"] == "werewolf")

    def reset_timer(self):
        self.phase_start_time = time.time()
        self.last_notify = self.phase_start_time    

    def get_villager_count(self) -> int:
        return sum(1 for actor in self.actors if self.actors[actor]["role"] == "villager" or self.actors[actor]["role"] == "seer")

    def phase_change(self, vote_result) -> bool:
        if vote_result:
            self.remove(vote_result, "killed")
            if vote_result in self.seer_targets: 
                del self.seer_targets[vote_result]
            kill_message = {"role": "system", "content": f"{vote_result} has been killed!\n\tRole: {self.actors[vote_result]['role']}."}
            self.send_to_room(self.night_room, kill_message, verbose=False)
            self.send_to_room(self.day_room, kill_message)

        self.clean_flagged_actors(verbose=False)

        wolf_count = self.get_wolf_count()
        villager_count = self.get_villager_count()

        # reached victory condition
        if wolf_count > villager_count or wolf_count == 0 or (self.phase == "day" and wolf_count == villager_count):
            if wolf_count == 0:
                self.log(Style.BRIGHT + role_colour("villager") + "Villagers win!" + Style.RESET_ALL)
            else:
                self.log(Style.BRIGHT + role_colour("werewolf") + "Werewolves win!" + Style.RESET_ALL)

            return True

        # game continues
        if self.phase == "night":
            self.phase = "day"
            self.current_room = self.day_room
            
        else:
            self.phase = "night"
            self.phase_number += 1
            self.current_room = self.night_room

        self.phase_header()



        if vote_result:
            day_message = f"You have met at the village tavern to discuss {vote_result}'s death.\n\t{wolf_count} werewolves remain.\n\t{villager_count} villagers remain."
        else:
            day_message = f"You have met at the village tavern.\n\tThe night was quiet.\n\t{wolf_count} werewolves remain.\n\t{villager_count} villagers remain."
        
        if self.phase_number == 1:
            day_message += "\n\tThis is the first day."

        if wolf_count == villager_count:
            day_message += "\n\tIf a werewolf is not lynched today, then the werewolves win!"

        if wolf_count == 1:
            night_message = f"You are the last remaining werewolf.\n\t{villager_count} villagers remain."
        else:
            night_message = f"You are meeting at the werewolf hideout.\n\t{villager_count} villagers remain."

        # put the actors to sleep and move them
        for actor in self.actors:
            self.send_sleep_message(actor)
            self.send_phase_message(actor, self.phase)
            role = self.actors[actor]["role"]

            if self.phase == "day":
                self.move_actor_to_room(actor, self.day_room.name, verbose=False)
                
                if role == "seer":
                    try:
                        target = random.choice(list(self.seer_targets.keys()))
                        self.send_to_actor(actor, {"role": "system", "content": f"Last night, you receieved a vision! {target} is a {self.seer_targets[target]}!"})
                        self.log(role_colour("seer") + actor + Style.RESET_ALL + f" recieved {target}'s role: " + role_colour(self.seer_targets[target]) + self.seer_targets[target] + Style.RESET_ALL)
                        del self.seer_targets[target]
                    except:
                        pass
                
                elif role == "villager":
                    self.send_to_actor(actor, {"role": "system", "content": "You were sleeping last night."})

            elif self.phase == "night" and role == "werewolf":
                self.move_actor_to_room(actor, self.night_room.name, verbose=False)

        # cleanup
        if self.phase == "day":
            self.send_to_room(self.day_room, {"role": "system", "content": day_message})
            self.phase_duration = self.DAY_PHASE_LENGTH
        else:
            self.send_to_room(self.night_room, {"role": "system", "content": night_message})
            self.phase_duration = self.NIGHT_PHASE_LENGTH

        self.reset_votes()
        self.reset_timer()
        self.awaken_room(self.current_room.name)



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

        self.seer_targets = {}

        roles_message = "Player roles:"

        for actor, role in zip(self.actors, roles):
            self.actors[actor]["role"] = role
            self.send_to_actor(actor, role, "role")
            colour = role_colour(role)
            roles_message += f"\n{actor} is a " + colour + role + Style.RESET_ALL

            if role != "seer":
                self.seer_targets[actor] = role

        self.log(roles_message)
        self.phase_header()

        for actor in self.actors:
            if self.actors[actor]["role"] == "werewolf":
                self.move_actor_to_room(actor, self.night_room.name, verbose=False)

        self.reset_votes()
        self.send_to_room(self.night_room.name, {"role": "system", "content": "You have arrived at the hideout to plot your first hunt."})
        self.awaken_room(self.night_room.name)            

        
        self.phase_start_time = time.time()
        self.last_notify = self.phase_start_time
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

                colour = role_colour(actor["role"])

                if msg["room"] == self.current_room.name:
                    if msg["action"] == "speak" and actor["can_speak"]:
                        speak_contest.add_speaker(msg["actor"], msg["content"], actor["charisma"], msg["room"], colour)
                    if "speech" in msg and msg["action"] != "speak" and actor["can_speak"]:
                        speak_contest.add_speaker(msg["actor"], msg["speech"], actor["charisma"], msg["room"], colour)
                    if msg["action"] == "yell":
                        self.yell(msg["actor"], msg["content"], colour)
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

            self.elapsed = int(time.time() - self.phase_start_time)

            if self.elapsed >= phase_duration and self.phase == "night":
                vote_result = resolve_majority_vote(self.voters, tiebreaker=True)
            elif self.elapsed >= phase_duration and self.phase == "day":
                vote_result = resolve_majority_vote(self.voters)
            else:
                vote_result = resolve_majority_vote(self.voters)

            if self.elapsed < phase_duration:
                if time.time() - self.last_notify >= self.NOTIFY_PERIOD or phase_duration - self.elapsed <= 5:
                    message = f"There are {phase_duration - self.elapsed} seconds remaining in the phase! Current vote target: {vote_result}"
                    self.send_to_room(self.current_room.name, {"role": "system", "content": message})
                    self.last_notify = time.time()

            # phase change
            if vote_result or self.elapsed >= phase_duration:
                self.end = self.phase_change(vote_result)
                if self.end:
                    break

            time.sleep(self.WAIT_TIME)
            # end main loop
            # TODO: make this smaller lol

        self.print_loop.join()


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
        Make note of other players and what roles you suspect they have.
        Remember what you were doing the previous night.
        """

        if self.role == "seer":
            new_message += "\nAs the seer, remember your visions."
        if self.role == "werewolf":
            new_message += "\nAs a werewolf, remember who your teammate is."
        
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

