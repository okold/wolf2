from multiprocessing import Process, Pipe
from threading import Thread, Lock
from multiprocessing.connection import Listener, Pipe, Connection
import time
from room import Room
import random
from llm import LLM
from datetime import datetime
from npc import create_npc_logger
from typing import Optional
from pydantic import BaseModel
from speech import SpeakingContest
import traceback

ADDRESS = ("localhost", 6000) #TODO: something about this

class ActionMessage(BaseModel):
    """
    The expected structure for messages passed to an from the server

    Args:
        action (str): specifies which function the server should call
        content (Optional[str]): supporting info for the action, like the item to give
        target (Optional[list[str]]): target(s) of the action, if applicable
        reason (Optional[str]): for analysis
        comment (Optional[str]): for actions that allow simultaneous speaking
        gesture (Optional[str]): for actions that allow simultaneous gesturing
    """
    action: str
    content: Optional[str] = None
    target: Optional[list[str]] = None
    reason: Optional[str] = None
    comment: Optional[str] = None
    gesture: Optional[str] = None

class World(Process):
    """
    The main server process for the game.

    Args:
        llm (LLM): used if the server needs to do any sort of NLP - OPTIONAL
        cli (Connection): a way for the CLI to influence the server - OPTIONAL
        default_room (Room): the Room that new Actors are inserted into - OPTIONAL
    """

    WAIT_TIME = 3 # wait period between "rounds"

    def __init__(self, llm: LLM = None, cli: Connection = None, default_room: Room = None):
        super().__init__()

        self.llm = llm                      # LLM information
        self.broadcast_log = []             # stores all broadcasts, TODO: clean this up at a certain length 
        self.cli = cli                      # connection to the terminal

        self.actors_lock = Lock()           # lock to access actors
        self.actors = {}                    # dictionary of actors
        self.flagged_actors = []            # list of tuples (actor, reason)
        self.listener = Listener(ADDRESS)   # for new connections

        # sets the default room
        if default_room == None:
            self.default_room = Room()
        else:
            self.default_room = default_room


        self.current_room = self.default_room

        timestamp = datetime.now()

        self.rooms_lock = Lock()
        self.rooms = {self.default_room.name: self.default_room}

        # TODO: change this. this is bad. it works.
        self.logger = create_npc_logger("World", timestamp)

        self.accept_connections = True
        self.connection_loop = Thread(target=self.new_connection_loop, daemon=True)

        self.print_info(f"Current Room: {self.default_room.name}")
        self.print_info(self.default_room.description)

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
                self.move_actor_to_room(actor["name"], self.default_room.name, verbose = False)
                
            

    def print_info(self, message: str):
        """
        Prints to the console and log (info)
        """
        self.logger.info(message)
        try:
            print(message["content"])
        except:
            pass

    # safely attempts a recv from the provided connection
    def try_recv(self, conn: Connection) -> ActionMessage:
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

    def send_summary_message(self, actor: str):
        try:
            with self.actors_lock:
                self.actors[actor]["conn"].send({"type": "summarize"})
        except Exception as e:
            self.logger.error(f"Failed to send message to actor {actor}: {e}")

    def send_phase_message(self, actor: str, phase : str):
        try:
            with self.actors_lock:
                self.actors[actor]["conn"].send({"type": "phase", "content": phase})
        except Exception as e:
            self.logger.error(f"Failed to send message to actor {actor}: {e}")

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
        #self.print_info(message)

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
                    self.print_info(message)
            except Exception as e:
                self.logger.error(f"Failed to send message to room {room}: {e}")

    def move_actor_to_room(self, actor: str, room: str, verbose = True):
        if room in self.rooms and actor in self.actors:
            old_room = self.actors[actor]["room"]
            self.actors[actor]["room"] = room
            if old_room in self.rooms:
                self.rooms[old_room].remove_actor(actor)  # <- this line is missing
            
            self.send_to_actor(actor, self.rooms[room].state(), "room")

            data = {
                "name": actor,
                "description": self.actors[actor]["description"],
                "status": self.actors[actor]["status"]
            }

            self.rooms[room].add_actor(data)
            arrival_message = f"{actor} has entered the {room}!"
            self.send_to_room(room, {"role": "user", "content": arrival_message})
            self.send_to_room(room, self.rooms[room].state(), "room", verbose=verbose)

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def yell(self, actor: str, content: str):
        """
        Broadcasts a message to everyone in the format:

        <actor> yells, "<content.upper()>!"

        Args:
            actor (str): the name of the yelling Actor
            content (str): the message they're yelling
        """
        output = f"{actor} yells, \"{content.upper()}\""
        self.send_to_room(self.actors[actor]["room"], {"role": "user", "content": output})

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

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def shoot(self, actor: str, target: str):
        """
        Lets the given actor try to shoot the target. 50% chance of success.

        Args:
            actor (str): the name of the shooting actor
            target (str): the name of the target
        """
        try:
            roll = random.randint(1,20)

            if roll >= 10:
                output = f"BANG! {actor} has shot at {target}, and hit!"
                self.send_to_room(self.actors[actor]["room"], {"role": "user", "content": output})
                self.remove(target, "killed")
            else:
                output = f"BANG! {actor} has shot at {target}, and missed!"
                self.send_to_room(self.actors[actor]["room"], {"role": "user", "content": output})
            
        except Exception as e:
            self.logger.warning(e)

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
                self.send_to_room(room, self.rooms[room].state(), "room")

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

    def run(self):
        connection_loop = Thread(target=self.new_connection_loop, daemon=True)
        connection_loop.start()

        # main loop
        while True:

            # logic for who gets to successfully speak this round
            speak_contest = SpeakingContest()

            # check for cli messages
            msg = self.try_recv(self.cli)
            if msg == "quit" or msg == "exit":
                break

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

            for msg in new_messages:
                if msg["room"] == self.current_room["name"]:
                    if msg["action"] == "speak" and self.actors[msg["actor"]]:
                        speak_contest.add_speaker(msg["actor"], msg["content"], self.actors[msg["actor"]]["charisma"], msg["room"])
                    if "comment" in msg and msg["action"] != "speak" and self.actors[msg["actor"]]["can_speak"]:
                        speak_contest.add_speaker(msg["actor"], msg["comment"], self.actors[msg["actor"]]["charisma"])
                    if msg["action"] == "yell":
                        self.yell(msg["actor"], msg["content"])
                    if msg["action"] == "gesture":
                        self.gesture(msg["actor"], msg["content"])
                    if "gesture" in msg and msg["action"] != "gesture":
                        self.gesture(msg["actor"], msg["gesture"])
                    if msg["action"] == "give":
                        self.give(msg["actor"], msg["content"], msg["target"])
                    if msg["action"] == "leave":
                        self.remove(msg["actor"])
                    if msg["action"] == "shoot":
                        self.shoot(msg["actor"], msg["target"])

            speak_output, speak_actor, interrupted_actors = speak_contest.resolve()

            if speak_output:
                room = self.actors[speak_actor]["room"]
                self.send_to_room(room, speak_output)
                for actor in interrupted_actors:
                    self.send_to_room(self.actors[speak_actor]["room"], {"role": "user", "content": f"{actor} was interrupted by {speak_actor}!"})
            
            self.clean_flagged_actors()    
            
            time.sleep(self.WAIT_TIME)
    
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