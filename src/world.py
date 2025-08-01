from multiprocessing import Process, Pipe
from threading import Thread, Lock
from queue import Queue
from multiprocessing.connection import Listener, Pipe, Connection
import time
import math
from room import Room
import random
from abc import ABC, abstractmethod
from llm import LLM
from colorama import Style
from datetime import datetime
from utils import create_logger
from speech import SpeakingContest
from collections import Counter

ADDRESS = ("localhost", 6000) #TODO: something about this

class World(Process, ABC):
    """
    The main server process for a game.

    Args:
        llm (LLM): used if the server needs to do any sort of NLP - OPTIONAL
        cli (Connection): a way for the CLI to influence the server - OPTIONAL
        default_room (Room): the Room that new Actors are inserted into - OPTIONAL
    """

    WAIT_TIME = 1 # wait period between "rounds"
    PRINT_COOLDOWN = 1 # just to make reading it less of a nightmare

    def __init__(self, llm: LLM = None, cli: Connection = None, default_room: Room = None, turn_based = False):
        super().__init__()

        self.llm = llm                      # LLM information
        self.cli = cli                      # connection to the terminal

        self.actors_lock = Lock()           # lock to access actors
        self.actors = {}                    # dictionary of actors
        self.flagged_actors = []            # list of tuples (actor, reason)
        self.listener = Listener(ADDRESS)   # for new connections

        self.print_queue = Queue()

        # sets the default room
        if default_room == None:
            self.default_room = Room()
        else:
            self.default_room = default_room


        self.current_room = self.default_room

        timestamp = datetime.now()

        self.rooms_lock = Lock()
        self.rooms = {self.default_room.name: self.default_room}

        self.logger = create_logger("World")

        self.accept_connections = True
        self.connection_loop = Thread(target=self.new_connection_loop, daemon=True)
        self.print_loop = Thread(target=self.print_loop, daemon=True)

        self.valid_vote_targets = []
        self.voters = {}

        self.end = False
        self.turn_based = turn_based

    def get_new_messages(self) -> list[dict]:
        new_messages = []

        # check each actor for messages & forward
        with self.actors_lock:
            for actor in self.actors:
                msg = self.try_recv(self.actors[actor]["conn"])
                if not msg:
                    pass
                else:
                    msg["actor"] = actor
                    new_messages.append(msg)

        return new_messages

    def log(self, message, print = True):
        """
        Logs immediately, and inserts into the print queue.
        """
        try:
            self.logger.info(message)
            self.print_queue.put(message)

        except:
            pass

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


    def new_connection_loop(self):
        """
        Adds new actors to the list. Upon connection, the next message from the actor must be its name.
        
        Duplicate names are not allowed.
        """
        while self.accept_connections:
            conn = self.listener.accept()


            actor = conn.recv()

            if actor["name"] in self.actors:
                conn.close() # TODO: error response for retries

            else:
                self.actors[actor["name"]] = actor
                actor["conn"] = conn
                actor["room"] = self.default_room.name
                conn.send(self.default_room.state())
                self.move_actor_to_room(actor["name"], self.default_room.name, notify = False)

    def try_recv(self, conn: Connection):
        """
        Safely attempts a recv.

        Args:
            conn (Connection): connection to test
        
        Returns:
            ActionMessage: may be None if the poll fails
        """
        try:
            if conn.poll():
                response = conn.recv()
                return response
            return None
        except Exception as e:
            self.logger.error(f"Failed to poll connection, creating leave message for actor. Error message: {e}")
            return {"action": "leave", "reason": "disconnect", "room": ""}
    
    def send_to_actor(self, actor : str, message: dict | str, type = "context"):
        """
        Attempts to send a message to the designated Actor

        Args:
            actor (str): the name of the Actor
            message (GPTMessage): a message ready to send to an LLM
            type (str): determines the function the Actor should call - OPTIONAL
        """
        try:
            with self.actors_lock:
                if isinstance(message, str) and type == "context":
                    message = {"role": "system", "content": message}
                self.actors[actor]["conn"].send({"type": type, "content": message})
        except Exception as e:
            self.logger.error(f"Failed to send message to actor {actor}: {e}")

    def send_act_token(self, actor: str):
        try:
            with self.actors_lock:
                self.actors[actor]["conn"].send({"type": "act_token"})
        except Exception as e:
            self.logger.error(f"Failed to send act token to actor {actor}: {e}")

    def send_summary_message(self, actor: str):
        try:
            with self.actors_lock:
                self.actors[actor]["conn"].send({"type": "summarize"})
        except Exception as e:
            self.logger.error(f"Failed to send summary message to actor {actor}: {e}")

    def send_sleep_message(self, actor: str):
        try:
            with self.actors_lock:
                self.actors[actor]["conn"].send({"type": "sleep"})
        except Exception as e:
            self.logger.error(f"Failed to send message to actor {actor}: {e}")
    
    def send_wake_message(self, actor: str):
        try:
            with self.actors_lock:
                self.actors[actor]["conn"].send({"type": "wake"})
        except Exception as e:
            self.logger.error(f"Failed to send message to actor {actor}: {e}")

    def awaken_room(self, room: str | Room):
        with self.rooms_lock:
            try:
                if isinstance(room, str):
                    for actor in self.rooms[room].actors:
                        self.send_wake_message(actor)
                elif isinstance(room, Room):
                    for actor in room.actors:
                        self.send_wake_message(actor)
            except Exception as e:
                self.logger.error(f"Failed to send message to room {room}: {e}")


    def sleep_room(self, room: str | Room):
        with self.rooms_lock:
            try:
                if isinstance(room, str):
                    for actor in self.rooms[room].actors:
                        self.send_sleep_message(actor)
                elif isinstance(room, Room):
                    for actor in room.actors:
                        self.send_sleep_message(actor)
            except Exception as e:
                self.logger.error(f"Failed to send message to room {room}: {e}")            

    def broadcast(self, message: str | dict, type = "context"):
        for actor in self.actors:
            self.send_to_actor(actor, message, type)

    def send_to_room(self, room: str | Room, message: dict, type = "context", verbose = True):
        with self.rooms_lock:
            try:
                if isinstance(room, str):
                    for actor in self.rooms[room].actors:
                        self.send_to_actor(actor, message, type)
                elif isinstance(room, Room):
                    for actor in room.actors:
                        self.send_to_actor(actor, message, type)
                if verbose:
                    self.log(message)
            except Exception as e:
                self.logger.error(f"Failed to send message to room {room}: {e}")

    def move_actor_to_room(self, actor: str, room: str, verbose = True, notify = True):
        if room in self.rooms and actor in self.actors:
            old_room = self.actors[actor]["room"]
            self.actors[actor]["room"] = room
            if old_room in self.rooms:
                self.rooms[old_room].remove_actor(actor)
            
            self.send_to_actor(actor, self.rooms[room].state(), "room")

            data = {
                "name": actor,
                "description": self.actors[actor]["description"],
                "status": self.actors[actor]["status"]
            }

            self.rooms[room].add_actor(data)
            arrival_message = f"{actor} has entered the {room}!"

            if notify:
                self.send_to_room(room, {"role": "user", "content": arrival_message}, verbose=verbose)
                self.send_to_room(room, self.rooms[room].state(), "room", verbose=False)

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def speak(self, actor: str, content: str, colour = None):
        output_plain = f"{actor} says, \"{content}\""
        self.send_to_room(self.actors[actor]["room"], {"role": "user", "content": output_plain}, verbose=False)

        if colour:
            output_fancy = colour + actor + Style.RESET_ALL + f" says, \"{content}\""
        else:
            output_fancy = output_plain
        
        self.log(output_fancy)

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def yell(self, actor: str, content: str, colour = None):
        """
        Broadcasts a message to everyone in the format:

        <actor> yells, "<content.upper()>!"

        Args:
            actor (str): the name of the yelling Actor
            content (str): the message they're yelling
        """
        output_plain = f"{actor} yells, \"{content.upper()}\""
        self.send_to_room(self.actors[actor]["room"], {"role": "user", "content": output_plain}, verbose=False)

        if colour:
            output_fancy = colour + actor + Style.RESET_ALL + " yells, " + Style.BRIGHT + "\"" + content.upper() + "\"" + Style.RESET_ALL
        else:
            output_fancy = f"{actor} yells, " + Style.BRIGHT + "\"" + content.upper() + "\"" + Style.RESET_ALL
        
        self.log(output_fancy)

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    # TODO: an ACTUAL inventory system. for now, it's just pretend.
    def give(self, actor: str, content: str, target: str):
        """
        Broadcasts than an actor has given an item to a target, in for format:

        <actor> gave a(n) <content> to <target>.

        Args:
            actor (str): the name of the giver
            content (str): the thing being given
            target (str): the recipient's name
        """
        if actor != target: #prevents people from giving themselves things
            output = f"{actor} gave a(n) {content} to {target}."
            self.send_to_room(self.actors[actor]["room"], {"role": "user", "content": output})
        else:
            self.logger.warning(f"Blocked {actor} from giving themselves something." )

    def remove(self, actor: str, reason: str = None):
        """
        Marks the actor to be removed from the room.

        Args:
            flagged_actors list[str, str]: a list of tuples of actor, reason
            actor (str): the name of the actor to remove
            reason (str): the reason they left i.e. "left", "killed"
        """
        if not reason:
            reason = "left"

        self.flagged_actors.append((actor, reason))

    def clean_flagged_actors(self, verbose = True):
        """
        Removes all actors in the flagged_actors list.
        """
        if self.flagged_actors:
            for flag in self.flagged_actors:
                try:
                    actor = flag[0]
                    reason = flag[1]
                    room = self.actors[actor]["room"]

                    self.actors[actor]["conn"].close()
                    self.actors.pop(actor, None)

                    if reason == "killed":
                        output = f"{actor} has been killed!"
                    else:
                        output = f"{actor} has left the room!"
                    
                    self.rooms[room].remove_actor(actor)

                    if verbose:
                        self.send_to_room(room, {"role": "user", "content": output})
                    
                except Exception as e:
                    self.logger.warning(e)
            for room in self.rooms:
                self.send_to_room(room, self.rooms[room].state(), "room", verbose=False)

            self.flagged_actors = []

    def gesture(self, actor: str, content: str):
        """
        Allows an actor to gesture in the format:

        <actor> <content> at <target>

        With the target being optional.

        Args:
            actor (str): the name of the actor acting
            content (str): the gesture being performed
        """
        self.send_to_room(self.actors[actor]["room"], {"role": "user", "content": f"{actor} {content}."})


    def vote(self, actor: str, target: str, validate = True, verbose = True):
        """
        
        """
        if target in self.valid_vote_targets or not validate:
            self.voters[actor] = target

            if verbose:
                message = f"{actor} has voted for {target}! The current votes are:"
                
                for voter in self.voters:
                    if self.voters[voter] != None:
                        message += f"\n\t{voter}: {self.voters[voter]}"

                self.logger.info(message)
                self.send_to_room(self.actors[actor]["room"],
                            {"role": "system", "content": message})


    def resolve_majority_vote(self, tiebreaker = False) -> str | None:
        """
        Returns the vote result with majority.
        If there's no clear majority (tie or no votes), returns None.
        Tiebreaker will resolve ties by choosing at random.
        """

        if not self.voters:
            return None
        
        if len(self.voters) == 1:
            for actor in self.voters:
                return self.voters[actor]
        
        #self.log(votes)

        vote_counts = Counter(self.voters.values())
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

    def reset_votes(self):
        """
        Empties the valid_vote_targets lits and voters dict
        """
        self.valid_vote_targets = []
        self.voters = {}

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def turn_based_loop(self):
        pass

    @abstractmethod
    def real_time_loop(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass
    
    def run(self):
        self.connection_loop.start()
        self.print_loop.start()

        self.setup()          

        if self.turn_based:
            self.turn_based_loop()
        else:
            self.real_time_loop()
        
        self.cleanup()

        self.print_loop.join()
    
if __name__ == "__main__":
    parent_conn, child_conn = Pipe()
    world = World(LLM(), child_conn)
    world.start()

    while True:
        msg = input()
        parent_conn.send(msg)
        if msg == "quit" or msg == "exit":
            break

    world.join()