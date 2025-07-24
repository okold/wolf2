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

        self.rooms_lock = Lock()
        self.rooms = {self.default_room.name: self.default_room}

        # TODO: change this. this is bad. it works.
        self.logger = create_npc_logger("World", timestamp)

        self.print_info(f"Current Room: {self.default_room.name}")
        self.print_info(self.default_room.description)

    def new_connection_loop(self):
        """
        Adds new actors to the list. Upon connection, the next message from the actor must be its name.
        
        Duplicate names are not allowed.
        """
        while True:
            conn = self.listener.accept()

            with self.actors_lock, self.rooms_lock:
                actor = conn.recv()

                if actor["name"] in self.actors:
                    conn.close() # TODO: error response for retries

                else:
                    self.actors[actor["name"]] = actor
                    actor["conn"] = conn
                    actor["room"] = self.default_room.name
                    conn.send(self.default_room.state())

                    arrival_message = f"{actor['name']} has entered the room! Description: {actor['description']}"
                    
                    self.default_room.add_actor({"name": actor["name"], "status": actor["status"], "description": actor["description"], "gender": actor["gender"]})
                    
            self.broadcast({"role": "user", "content": arrival_message})
            self.broadcast(self.default_room.state(), "room")
            time.sleep(5)

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
            return {"action": "leave", "reason": "disconnect"}
    
    def send_to_actor(self, actor : str, message: dict, type = "context"):
        """
        Attempts to send a message to the designated Actor

        Args:
            actor (str): the name of the Actor
            message (GPTMessage): a message ready to send to an LLM
            type (str): determines the function the Actor should call - OPTIONAL
        """
        try:
            with self.actors_lock:
                self.actors[actor]["conn"].send({"type": type, "content": message})
        except Exception as e:
            self.logger.error(f"Failed to send message to actor {actor}: {e}")

    def broadcast(self, message: dict, type = "context"):
        for actor in self.actors:
            self.send_to_actor(actor, message, type)
        self.print_info(message)

    def send_to_room(self, room: str, message: dict, type = "context"):
        with self.rooms_lock:
            try:
                for actor in self.rooms[room].actors:
                    self.send_to_actor(actor, message, type)
                self.print_info(message)
            except Exception as e:
                self.logger.error(f"Failed to send message to room {room}: {e}")

    def move_actor_to_room(self, actor: str, room: str):
        with self.rooms_lock, self.actors_lock:
            if room in self.rooms and actor in self.actors:
                    self.actors["room"] = room

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

    def clean_flagged_actors(self):
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

                    self.send_to_room(self.actors[actor]["room"], {"role": "user", "content": output})
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
                if msg["action"] == "speak" and self.actors[msg["actor"]]["can_speak"]:
                    speak_contest.add_speaker(msg["actor"], msg["content"], self.actors[msg["actor"]]["charisma"])
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

            # outputs speak messages
            # TODO: figure this out better
            if speak_contest.speak_output:
                self.send_to_room(self.actors[speak_contest.speak_actor]["room"], speak_contest.speak_output)
                for actor in speak_contest.interrupted_actors:
                    self.send_to_room(self.actors[speak_contest.speak_actor]["room"], {"role": "user", "content": f"{actor} was interrupted by {speak_contest.speak_actor}!"})
            
            self.clean_flagged_actors()    
            
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