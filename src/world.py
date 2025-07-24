from multiprocessing import Process, Pipe
from threading import Thread, Lock
from multiprocessing.connection import Listener, Pipe, Connection
import time
from room import Room
import random
from llm import LLM, GPTMessage
from datetime import datetime
from npc import create_npc_logger
from typing import Optional
from pydantic import BaseModel

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

        timestamp = datetime.now()

        # TODO: change this. this is bad. it works.
        self.logger = create_npc_logger("World", timestamp)

        self.print_info(f"Current Room: {self.default_room.name}")
        self.print_info(self.default_room.description)

    def print_info(self, message: str):
        """
        Prints to the console and log (info)
        """
        self.logger.info(message)
        print(message)

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
            return {"action": "leave", "reason": "disconnect"}
    
    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def send_to_actor_unsafe_(self, actor : str, message: GPTMessage, type = "context"):
        """
        Attempts to send a message to the designated Actor

        Args:
            actor (str): the name of the Actor
            message (GPTMessage): a message ready to send to an LLM
            type (str): determines the function the Actor should call - OPTIONAL
        """
        try:
            self.actors[actor]["conn"].send({"type": type, "content": message})
        except Exception as e:
            self.logger.error(f"Failed to send message to {actor}: {e}")

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def broadcast_unsafe_(self, content: str, role = "user", exclude_actors: list[str] = [], block_duplicates = True):
        """
        Sends a string to every Actor connected to the world.

        Args:
            content (str): the string to send to the Actors
            role (str): the role for the resulting GPTMessage, default "user"
            exclude_actors (list[str]): actors to exclude from the broadcast - OPTIONAL
            block_duplicates (bool): will refuse to send the same message twice if True - OPTIONAL
        """

        if content not in self.broadcast_log or not block_duplicates:
            self.print_info(content)
            if block_duplicates:
                self.broadcast_log.append(content)
            for actor in self.actors:
                if actor not in exclude_actors:
                    self.send_to_actor_unsafe_(actor, {"role": role, "content": content})
        else:
            self.logger.warning(f"Blocked duplicate broadcast: {content}")

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def broadcast_room_state_unsafe_(self):
        """
        Broadcasts the room state to all actors connected to the server.
        """
        for actor in self.actors:
            self.actors[actor]["conn"].send({"type": "room", "content": self.default_room.dict()})

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def yell_unsafe_(self, actor: str, content: str):
        """
        Broadcasts a message to everyone in the format:

        <actor> yells, "<content.upper()>!"

        Args:
            actor (str): the name of the yelling Actor
            content (str): the message they're yelling
        """
        output = f"{actor} yells, \"{content.upper()}\""
        self.broadcast_unsafe_(output)

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    # TODO: an ACTUAL inventory system. for now, it's just pretend.
    def give_unsafe_(self, actor: str, content: str, target: str):
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
            self.broadcast_unsafe_(output)
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
    def shoot_unsafe_(self, actor: str, target: str):
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
                self.broadcast_unsafe_(output, block_duplicates=False)
                self.remove(actor, "killed")
            else:
                output = f"BANG! {actor} has shot at {target}, and missed!"
                self.broadcast_unsafe_(output, block_duplicates=False)
            
        except Exception as e:
            self.logger.warning(e)

    def clean_flagged_actors_unsafe_(self):
        """
        Removes all actors in the flagged_actors list.
        """
        if self.flagged_actors:
            for actor in self.flagged_actors:
                try:
                    self.actors[actor[0]]["conn"].close()
                    self.actors.pop(actor[0], None)

                    if actor[1] == "killed":
                        output = f"{actor[0]} has been killed!"
                        self.default_room.kill_actor(actor[0])
                    else:
                        output = f"{actor[0]} has left the room!"
                        self.default_room.remove_actor(actor[0])

                    self.broadcast_unsafe_(output)
                except Exception as e:
                    self.logger.warning(e)

            self.broadcast_room_state_unsafe_()
            self.flagged_actors = []

    def new_connection_loop(self):
        """
        Adds new actors to the list. Upon connection, the next message from the actor must be its name.
        
        Duplicate names are not allowed.
        """
        while True:
            conn = self.listener.accept()

            self.actors_lock.acquire()

            actor = conn.recv()

            if actor["name"] in self.actors:
                conn.close() # TODO: error response for retries

            else:
                self.actors[actor["name"]] = actor
                actor["conn"] = conn
                conn.send(self.default_room.dict())

                arrival_message = f"{actor['name']} has entered the room!"
                self.broadcast_unsafe_(arrival_message)
                self.default_room.add_actor({"name": actor["name"], "status": actor["status"]})
                self.broadcast_room_state_unsafe_()
            
            self.actors_lock.release()

    def gesture_unsafe_(self, actor: str, content: str):
        """
        Allows an actor to gesture in the format:

        <actor> <content> at <target>

        With the target being optional.

        Args:
            actor (str): the name of the actor acting
            content (str): the gesture being performed
        """

        self.broadcast_unsafe_(f"{actor} {content}.")

    class SpeakingContest():
        def __init__(self):
            self.max_cha = 0
            self.speak_output = None
            self.speak_actor = None
            self.interrupted_actors = []

        def add_speaker(self, actor, speech, charisma):
            if charisma > self.max_cha:
                self.speak_output = f"{actor} says, \"{speech}\""
                self.max_cha = charisma

                if self.speak_actor != None:
                    self.interrupted_actors.append(self.speak_actor)

                self.speak_actor = actor
            else:
                self.interrupted_actors.append(actor)

    def run(self):
        connection_loop = Thread(target=self.new_connection_loop, daemon=True)
        connection_loop.start()

        # main loop
        while True:

            # logic for who gets to successfully speak this round
            speak_contest = self.SpeakingContest()

            # check for cli messages
            msg = self.try_recv(self.cli)
            if msg == "quit" or msg == "exit":
                break

            # check each actor for messages & forward
            self.actors_lock.acquire()
            for actor in self.actors:
                msg = self.try_recv(self.actors[actor]["conn"])
                if not msg:
                    pass
                else:
                    if msg["action"] == "speak":
                        speak_contest.add_speaker(actor, msg["content"], self.actors[actor]["charisma"])
                    if "comment" in msg and msg["action"] != "speak":
                        speak_contest.add_speaker(actor, msg["comment"], self.actors[actor]["charisma"])
                    if msg["action"] == "yell":
                        self.yell_unsafe_(actor, msg["content"])
                    if msg["action"] == "gesture":
                        self.gesture_unsafe_(actor, msg["content"])
                    if "gesture" in msg and msg["action"] != "gesture":
                        self.gesture_unsafe_(actor, msg["gesture"])
                    if msg["action"] == "give":
                        self.give_unsafe_(actor, msg["content"], msg["target"])
                    if msg["action"] == "leave":
                        self.remove(actor)
                    if msg["action"] == "shoot":
                        self.shoot_unsafe_(actor, msg["target"])

            # outputs speak messages
            # TODO: figure this out better
            if speak_contest.speak_output:
                self.broadcast_unsafe_(speak_contest.speak_output)
                for actor in speak_contest.interrupted_actors:
                    self.broadcast_unsafe_(f"{actor} was interrupted by {speak_contest.speak_actor}!")
            
            self.clean_flagged_actors_unsafe_()    
            self.actors_lock.release()
            
            time.sleep(World.WAIT_TIME)

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