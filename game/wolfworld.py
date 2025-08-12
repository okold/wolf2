from multiprocessing.connection import Connection

from random import random
import random
import time
import sys
import os
import csv
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
from utils import CSVLogger
from world import World
from room import Room, load_room

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

    PLAYER_COUNT = 8
    NUM_WOLVES = 2

    # real-time mode
    NIGHT_PHASE_LENGTH = 60
    DAY_PHASE_LENGTH = 120
    NOTIFY_PERIOD = 30

    #turn-based mode
    NIGHT_ROUNDS = 4
    DAY_ROUNDS = 4


    def __init__(self, cli: Connection = None, csv_logger = None, txt_logger = None, wolf_strategy="window", village_strategy="window", seed=1234, listener=None):

        self.day_room = load_room("game/tavern.json")
        self.night_room = load_room("game/cave.json")

        # note to self: I init to the day room because then the villagers don't
        # start in the hideout... haha
        super().__init__(cli = cli, default_room=self.day_room, turn_based=True, csv_logger=csv_logger, txt_logger=txt_logger, seed=seed, listener=listener)

        self.csv_logger = csv_logger
        self.rooms[self.night_room.name] = self.night_room
        self.current_room = self.night_room
        self.phase = "night"
        self.phase_number = 1
        self.seer_targets = {}
        self.wolf_strategy = wolf_strategy
        self.village_strategy = village_strategy
        self.seer_alive = True
        self.werewolves = []

    ### CORE FUNCTIONALITY (ABSTRACT METHODS)
    def setup(self):
        while True:
            with self.actors_lock:
                if len(self.actors) == self.PLAYER_COUNT:
                    self.accept_connections = False
                    break
            time.sleep(1)

        roles = ["werewolf"] * self.NUM_WOLVES + ["villager"] * (self.PLAYER_COUNT - self.NUM_WOLVES - 1) + ["seer"]
        random.shuffle(roles)

        for actor in self.actors:
            self.send_sleep_message(actor)

        self.seer_targets = {}

        roles_message = "Player roles:"

        for actor, role in zip(self.actors, roles):
            self.actors[actor]["role"] = role
            self.send_to_actor(actor, role, "role")
            if normalize_role(role) == "werewolf":
                self.send_strategy_message(actor, self.wolf_strategy)
                self.werewolves.append(actor)
            elif normalize_role(role) == "villager":
                self.send_strategy_message(actor, self.village_strategy)
            colour = role_colour(role)
            roles_message += f"\n{actor} is a " + colour + role + Style.RESET_ALL + f": {self.actors[actor]['description']}"
            
            if role != "seer":
                self.seer_targets[actor] = role

        for werewolf in self.werewolves:
            self.send_team_message(werewolf, self.werewolves)

        self.log(roles_message)
        self.phase_header()

        for actor in self.actors:
            if self.actors[actor]["role"] == "werewolf":
                self.move_actor_to_room(actor, self.night_room.name, verbose=False)


        for actor in self.actors:
            self.send_phase_message(actor, self.phase)
        self.send_to_room(self.night_room.name, {"role": "system", "content": "This is the first night!\n\tYou've scoped out your targets, and have returned to vote for who seems tastiest!"})
        self.reset_votes()
        self.awaken_room(self.night_room.name)  

        self.log_csv(action="start_game")
        
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

                round_message = None

                if round == 1:
                    round_message = f"Turn order: {turn_order}"

                if round == num_rounds - 1:
                    round_message = "This is the penultimate round! Make your final decisions!"

                if round == num_rounds:
                    round_message = "This is your final chance to act! Cast your votes now!"

                if round_message:
                    self.send_to_room(self.current_room, {"role": "system", "content": round_message})

                for name in turn_order:
                    actor = self.actors[name]

                    colour = role_colour(actor["role"])

                    self.send_act_token(name)
                    self.log_csv(action="send_act_token", target=name)

                    msg = actor["conn"].recv()

                    #print(msg)

                    if msg["action"] == "speak":
                        try:
                            reason = msg["reason"]
                        except:
                            reason = None

                        self.speak(name, msg["content"], colour, reason=reason)
                        self.log_csv(actor=name, action="speak", content=msg["content"], role=self.actors[name]["role"])

                    if msg["action"] == "vote":
                        if actor["name"] != msg["content"] and msg["content"] != self.voters[actor["name"]] and msg["content"] in self.valid_vote_targets:
                            self.vote(name, msg["content"], msg["reason"])
                            self.log_csv(actor=name, action="vote", target=msg["content"], role=self.actors[name]["role"])
                            vote_result = self.resolve_majority_vote()
                            if vote_result:
                                break
                        else:
                            self.send_to_actor(name, {"role": "system", "content": "ERROR processing your vote! You must provide a single name, example: 'Bob', you may not vote for yourself, and you may not vote for the same target twice."})
                            self.send_to_room(self.current_room, {"role": "user", "content": f"{name} is quiet."})

                    if msg["action"] == "pass":
                        self.send_to_room(self.current_room, {"role": "user", "content": f"{name} is quiet."})

                # after everyone has acted, if a vote has passed, end the phase.
                if vote_result:
                    break
            
            # force a tiebreaker at night
            if not vote_result and self.phase == "night":
                vote_result = self.resolve_majority_vote(tiebreaker=True)

            self.end = self.phase_change(vote_result)
        
            time.sleep(self.WAIT_TIME)

    def real_time_loop(self):
        pass

    def cleanup(self):
        try:
            self.flagged_actors = self.actors.keys()
            self.clean_flagged_actors()
        except:
            pass

        try:
            self.listener.close()
        except:
            pass

    def vote(self, actor: str, target: str, reason: str, validate = True, verbose = True):
        if target in self.valid_vote_targets or not validate:
            self.voters[actor] = target

            if verbose:
                if self.phase == "night":
                    message = f"{actor} has voted to hunt {target}! Reason: {reason}"
                else:
                    message = f"{actor} has voted to lynch {target}! Reason: {reason}"

                #self.logger.info(message)
                self.send_to_room(self.actors[actor]["room"],{"role": "user", "content": message}, excludes=[actor])
                self.send_to_room(self.actors[actor]["room"], message=self.voters, type="vote_state", verbose=False)

    # HELPER METHODS

    def log_csv(self, actor="World", action="", content="", target="", tokens_in=0, tokens_out=0, eval_in=0, eval_out=0, role=""):
        self.csv_logger.log(actor=actor, action=action, content=content, target=target, phase=self.phase, phase_num=self.phase_number, tokens_in=tokens_in, tokens_out=tokens_out, eval_in=eval_in, eval_out=eval_out, role=role)

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
                    elif self.phase == "night" and role == "werewolf":
                        self.voters[actor] = None

            #print(f"{self.valid_vote_targets}. {self.voters}")
        
        if self.phase == "day":
            self.send_to_room(self.day_room.name, self.valid_vote_targets, "vote_targets", verbose=False)
            self.send_to_room(self.day_room.name, message=self.voters, type="vote_state", verbose=False)

        else:
            self.send_to_room(self.night_room.name, self.valid_vote_targets, "vote_targets", verbose = False)
            self.send_to_room(self.night_room.name, message=self.voters, type="vote_state", verbose=False)

    def force_summary(self): 
        self.log({"role": "system", "content": "Preparing for the next round... Please be patient."})

        summarizing_actors = []

        for actor in self.actors:
            if normalize_role((self.actors[actor]["role"]) == "villager" and self.phase_number != 1) or normalize_role(self.actors[actor]["role"]) == "werewolf":
                self.send_summary_message(actor)
                summarizing_actors.append(actor)

        while True:
            ready_actors = []

            for actor in summarizing_actors:
                response = self.try_recv(self.actors[actor]["conn"])
                if response:
                    ready_actors.append(actor)
                    self.log({"role": "system", "content": f"{actor} is ready!"})
                
            summarizing_actors = [name for name in summarizing_actors if name not in ready_actors]

            if summarizing_actors == []:
                break
            else:
                time.sleep(1)

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
            if vote_result in self.werewolves:
                self.werewolves.remove(vote_result)
                for werewolf in self.werewolves:
                    self.send_team_message(werewolf, self.werewolves)
            if vote_result in self.seer_targets: 
                del self.seer_targets[vote_result]
            kill_message = {"role": "user", "content": f"{vote_result}, a {self.actors[vote_result]['role']}, has been killed!"}
            self.send_to_room(self.night_room, kill_message, verbose=False)
            self.send_to_room(self.day_room, kill_message)
            self.log_csv(action="declare_vote_result", role=self.actors[vote_result]["role"], target=vote_result)

            if self.actors[vote_result]['role'] == "seer":
                self.seer_alive = False

        self.clean_flagged_actors(verbose=False)

        wolf_count = self.get_wolf_count()
        villager_count = self.get_villager_count()

        # reached victory condition
        if wolf_count >= villager_count or wolf_count == 0 or (self.phase == "day" and wolf_count == villager_count):
            if wolf_count == 0:
                self.log_csv(action="declare_winner", content="village")
                self.log(Style.BRIGHT + role_colour("villager") + "Villagers win!" + Style.RESET_ALL)
            else:
                self.log_csv(action="declare_winner", content="werewolves")
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
        self.log_csv(action="phase_change")

        if vote_result:
            day_message = f"You have met at the village tavern.\n\t{vote_result} was found dead in the morning, as if mauled by a beast."
        else:
            day_message = f"You have met at the village tavern.\n\tThe night was quiet."
        
        if self.seer_alive:
            day_message += "\n\tThe seer still lives!"
        else:
            day_message += "\n\tWoe, for the seer is dead!"

        day_message += f"\n\t{wolf_count} werewolves remain.\n\t{villager_count} villagers remain.\n\tVote for who to lynch!"

        if self.phase_number == 1:
            day_message += "\n\tThis is the first day."

        if wolf_count == villager_count - 1:
            day_message += "\n\tIf a werewolf is not lynched today, then the werewolves will wipe out the village!"


        if wolf_count == 1:
            night_message = f"You are the last remaining werewolf, hiding alone in the cave. Vote for your next kill! \n\t{villager_count} villagers remain."
        else:
            night_message = f"You are meeting at the hideout with your pack. Vote for your next kill! \n\t{villager_count} villagers remain."

        if self.seer_alive:
            night_message += "\n\tThe seer still lives! Who could it be?"
        else:
            night_message += "\n\tRejoice, for the seer is dead!"

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
                        self.log_csv(action="seer_vision", content=f"{target}", target=actor, role=self.seer_targets[target])
                        del self.seer_targets[target]
                    except:
                        pass
                
                elif role == "villager":
                    villager_message = "You were sleeping last night."
                    if vote_result:
                        villager_message += " You heard the howling of wolves at night."
                    else:
                        villager_message += " The night was eerily quiet."

                    self.send_to_actor(actor, {"role": "system", "content": villager_message})

            elif self.phase == "night" and role == "werewolf":
                self.move_actor_to_room(actor, self.night_room.name, verbose=False)

        for actor in self.actors:
            self.send_phase_message(actor, self.phase)

        self.reset_votes()

        # cleanup
        if self.phase == "day":
            self.send_to_room(self.day_room, {"role": "system", "content": day_message})
            self.force_summary()
        else:
            self.send_to_room(self.night_room, {"role": "system", "content": night_message})


        self.awaken_room(self.current_room.name)

    