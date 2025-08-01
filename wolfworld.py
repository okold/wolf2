from multiprocessing.connection import Connection

from random import random

import random
import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from npc import NPC
from world import World
from room import Room

from speech import SpeakingContest
from colorama import Fore, Style

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

    PLAYER_COUNT = 6
    NUM_WOLVES = 2

    # real-time mode
    NIGHT_PHASE_LENGTH = 60
    DAY_PHASE_LENGTH = 120
    NOTIFY_PERIOD = 30

    #turn-based mode
    NIGHT_ROUNDS = 5
    DAY_ROUNDS = 4


    def __init__(self, cli: Connection = None, turn_based = False):

        self.day_room = Room("Village Tavern", "The village's official meeting place.")
        self.night_room = Room("Hideout", "A cave on the outskirts of the village.")

        # note to self: I init to the day room because then the villagers don't
        # start in the hideout... haha
        super().__init__(cli = cli, default_room=self.day_room, turn_based=turn_based)

        self.rooms[self.night_room.name] = self.night_room
        self.current_room = self.night_room
        self.phase = "night"
        self.phase_number = 1
        self.seer_targets = {}

    ### CORE FUNCTIONALITY (ABSTRACT METHODS)
    def setup(self):
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
        self.send_to_room(self.night_room.name, {"role": "system", "content": "You have arrived at the hideout to plot your first hunt. Choose a villager to kill!"})
        self.awaken_room(self.night_room.name)  
        
    def turn_based_loop(self):

        while not self.end:

            turn_order = []
            vote_result = None

            if self.phase == "night":
                turn_order = [actor for actor in self.actors if self.actors[actor]["role"] == "werewolf"]
                random.shuffle(turn_order)
                num_rounds = self.NIGHT_ROUNDS
            else:
                turn_order = [actor for actor in self.actors]
                random.shuffle(turn_order)
                num_rounds = self.DAY_ROUNDS

            for round in range(1, num_rounds+1):

                round_message = f"Beginning Round {round}/{num_rounds}"

                if round == 1:
                    round_message += f"\n\tTurn Order: {turn_order}"

                if round == num_rounds:
                    round_message += "\n\tThis is the FINAL ROUND! Vote if needed!"

                self.send_to_room(self.current_room, {"role": "system", "content": round_message})

                for name in turn_order:
                    actor = self.actors[name]

                    colour = role_colour(actor["role"])

                    self.send_act_token(name)
                    msg = actor["conn"].recv()

                    if msg["action"] == "speak":
                        self.speak(name, msg["content"], colour)
                    if msg["action"] == "vote":
                        self.vote(name, msg["content"])
                        vote_result = self.resolve_majority_vote()
                        if vote_result:
                            break
                    if msg["action"] == "pass":
                        self.send_to_room(self.current_room, {"role": "user", "content": f"{name} is quiet."})

                if vote_result:
                    break
            
            if not vote_result and self.phase == "night":
                vote_result = self.resolve_majority_vote(tiebreaker=True)

            self.end = self.phase_change(vote_result)
        
            time.sleep(self.WAIT_TIME)

            


    def real_time_loop(self):
        self.phase_start_time = time.time()
        self.last_notify = self.phase_start_time
        phase_duration = self.NIGHT_PHASE_LENGTH

        # main loop
        while True:
            # logic for who gets to successfully speak this round
            speak_contest = SpeakingContest()
        
            new_messages = self.get_new_messages()

            for msg in new_messages:

                actor = self.actors[msg["actor"]]

                colour = role_colour(actor["role"])

                if msg["action"] == "speak" and actor["can_speak"]:
                    speak_contest.add_speaker(msg["actor"], msg["content"], actor["charisma"], colour)
                if msg["speech"] and msg["action"] != "speak" and actor["can_speak"]:
                    speak_contest.add_speaker(msg["actor"], msg["speech"], actor["charisma"], colour)
                if msg["action"] == "yell":
                    self.yell(msg["actor"], msg["content"], colour)
                if msg["action"] == "gesture":
                    self.gesture(msg["actor"], msg["content"])
                if "gesture" in msg and msg["action"] != "gesture":
                    self.gesture(msg["actor"], msg["gesture"])
                if msg["action"] == "vote":
                    self.vote(msg["actor"], msg["target"])

            speak_output_plain, speak_output_colour, speak_actor, interrupted_actors = speak_contest.resolve()

            if speak_output_plain:
                room = self.actors[speak_actor]["room"]
                self.send_to_room(room, speak_output_plain, verbose=False)
                self.log(speak_output_colour)
                for actor in interrupted_actors:
                    self.send_to_room(room, {"role": "user", "content": f"{actor} was interrupted by {speak_actor}!"}, verbose=False)

            self.elapsed = int(time.time() - self.phase_start_time)

            if self.elapsed >= phase_duration and self.phase == "night":
                vote_result = self.resolve_majority_vote(tiebreaker=True)
            elif self.elapsed >= phase_duration and self.phase == "day":
                vote_result = self.resolve_majority_vote()
            else:
                vote_result = self.resolve_majority_vote()

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

    def cleanup(self):
        pass

    # HELPER METHODS

    def send_phase_message(self, actor: str, phase : str):
        try:
            with self.actors_lock:
                self.actors[actor]["conn"].send({"type": "phase", "content": phase})
        except Exception as e:
            self.logger.error(f"Failed to send message to actor {actor}: {e}")

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

    def reset_timer(self):
        self.phase_start_time = time.time()
        self.last_notify = self.phase_start_time    

    def phase_header(self):
        self.log(f"-------------\033[1m{self.phase.upper()} {self.phase_number}: {self.current_room.name.upper()}\033[0m---\n{self.current_room.description}")

    def get_wolf_count(self) -> int:
        return sum(1 for actor in self.actors if self.actors[actor]["role"] == "werewolf")

    def get_villager_count(self) -> int:
        return sum(1 for actor in self.actors if self.actors[actor]["role"] == "villager" or self.actors[actor]["role"] == "seer")

    def phase_change(self, vote_result) -> bool:
        if vote_result:
            self.remove(vote_result, "killed")
            if vote_result in self.seer_targets: 
                del self.seer_targets[vote_result]
            kill_message = {"role": "user", "content": f"{vote_result}, a {self.actors[vote_result]['role']}, has been killed!"}
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
            night_message = f"You are the last remaining werewolf. Vote for your next kill! \n\t{villager_count} villagers remain."
        else:
            night_message = f"You are meeting at the werewolf hideout. Vote for your next kill! \n\t{villager_count} villagers remain."

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
                        self.send_to_actor(actor, {"role": "user", "content": f"Last night, you receieved a vision! {target} is a {self.seer_targets[target]}!"})
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

            if not self.turn_based:
                self.phase_duration = self.DAY_PHASE_LENGTH
        else:
            self.send_to_room(self.night_room, {"role": "system", "content": night_message})

            if not self.turn_based:
                self.phase_duration = self.NIGHT_PHASE_LENGTH

        self.reset_votes()

        if not self.turn_based:
            self.reset_timer()

        self.awaken_room(self.current_room.name)

    