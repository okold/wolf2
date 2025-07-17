from multiprocessing import Process, Pipe
from threading import Thread, Lock
from multiprocessing.connection import Listener, Pipe
import time
import logging
from actor import Actor
import random
from llm import LLM
from datetime import datetime

ADDRESS = ("localhost", 6000)

### World
# The main server process for the game. Can receive messages from the 
class World(Process):

    WAIT_TIME = 3 # wait period between "rounds"

    def __init__(self, cli, default_room = None):
        super().__init__()

        self.llm = LLM()
        self.output_log = []

        # for cli
        self.cli = cli

        # actors and connection stuff
        self.actors_lock = Lock()
        self.actors = {}
        self.listener = Listener(ADDRESS)

        if default_room == None:
            self.default_room = Room()
        else:
            self.default_room = default_room

        self.print_info(f"Current Room: {self.default_room.name}")
        self.print_info(self.default_room.description)

    def print_info(self, message):
        logging.info(message)
        print(message)

    # safely attempts a recv from the provided connection
    def try_recv(self, conn):
        try:
            if conn.poll():
                response = conn.recv()
                return response
            return None
        except Exception as e:
            logging.error(f"Failed to poll connection, creating leave message for actor. Error message: {e}")
            return {"action": "leave"}
    
    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def send_to_actor(self, actor, message, role = "user"):
        self.actors[actor]["conn"].send({"role": role, "content": message})

    # NOTE: this is NOT THREAD SAFE, and is intended to be called already within a lock
    def broadcast(self, message, role = "user", exclude_actors = [], block_duplicates = True):
        if message not in self.output_log or not block_duplicates:
            self.print_info(message)
            if block_duplicates:
                self.output_log.append(message)
            for actor in self.actors:
                if actor not in exclude_actors:
                    self.send_to_actor(actor, message, role)
        else:
            logging.warning(f"Blocked duplicate broadcast: {message}")

    def run(self):

        # thread for new connections
        # the actor's next message after accepting must be the desired name
        # for now, closes connection if the name is a duplicate
        def listen_loop():
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
                    self.broadcast(arrival_message)
                
                self.actors_lock.release()

        listener_thread = Thread(target=listen_loop, daemon=True)
        listener_thread.start()

        # main loop
        while True:

            # logic for who gets to successfully speak this round
            max_cha = 0
            speak_output = None
            speak_actor = None
            interrupted_actors = []

            flagged_actors = [] # flag bad connections for removal

            # check for cli messages
            msg = self.try_recv(self.cli)
            if msg == "quit" or msg == "exit":
                break

            # check each actor for messages & forward
            self.actors_lock.acquire()
            for actor in self.actors:
                msg = self.try_recv(self.actors[actor]["conn"])
                if msg == None:
                    pass

                ### speak
                # { "action": "speak", "content": "I am saying something!"}
                # Echoes the content to the rest of the room.
                # Only the actor with the highest cha goes through
                # Message is sent at the end of the main loop
                elif msg["action"] == "speak":
                    if self.actors[actor]["cha"] > max_cha:
                        speak_output = f"{actor} says, \"{msg['content']}\""
                        max_cha = self.actors[actor]["cha"]

                        if speak_actor != None:
                            interrupted_actors.append(actor)

                        speak_actor = actor
                    else:
                        interrupted_actors.append(actor)

                ### yell
                # { "action": "yell", "content": "HANDS IN THE AIR! THIS IS A HOLD-UP!" }
                # Unlike speak, always broadcasts.
                elif msg["action"] == "yell":
                    output = f"{actor} yells, \"{msg['content'].upper()}\""
                    self.broadcast(output)

                ### give
                # { "action": "give", "content": "whiskey", "target": "Bandit" }
                # TODO: an ACTUAL inventory system. for now, it's just pretend.
                elif msg["action"] == "give":
                    if actor != msg["target"]: #prevents people from giving themselves things
                        output = f"{actor} gave a(n) {msg['content']} to {msg['target']}"
                        self.broadcast(output)
                    else:
                        logging.warning(f"Blocked {actor} from giving themselves something." )

                ### skill_check
                # { "action": "skill", "content": "play the piano" }
                elif msg["action"] == "skill":
                    system_message = f"""Translate a skill check into a sentence. You may determine success or failure.

                    Example input (success):
                    "action": "skill", "content": "play the piano" 
                    actor: "name": "Robin", "str": 7, "int": 11, "cha": "14", "lck": "10"

                    Example output (success):
                    Robin skillfuly played an upbeat tune on the piano.

                    Example input (failure):
                    "action": "skill", "content": "arm wrestle"
                    actor: "name": "Robin", "str": 7, "int": 11, "cha": "14", "lck": "10"
                    target: "name": "Mick", "str": 14, "int": 10, "cha": "12", "lck": "8"

                    Example output (failure):
                    Try as she might, Robin couldn't beat Mick at an arm wrestle!
                    """

                    prompt = [
                        { "role": "developer", "content": system_message},
                        { "role": "user", "content": f"{msg}"},
                        { "role": "user", "content": f"actor: {self.actors[actor]}"}
                    ]

                    try:
                        if msg["target"] and msg["target"] != "self":
                            prompt += [{"role": "user", "content": f"target: {self.actors[msg['target']]}"}]
                    except KeyError:
                        pass # usually just means the LLM is trying something like "everyone"

                    response = self.llm.prompt(prompt)
                    output = response.output_text

                    self.broadcast(output)
                            
                ### challenge
                # { "action": "challenge", "content": "dance", "target": "Bandit"}
                # TODO: STUB
                elif msg["action"] == "challenge":
                    pass

                ### leave
                # { "action": "leave" }
                # Flags the requesting actor for clearing.
                # Leavers are broadcast at the end of the loop
                elif msg["action"] == "leave":
                    flagged_actors.append((actor, "left"))

                ### shoot
                # { "action": "shoot", "target": "Bandit", "reason": "Enforcing the law." }
                # Shooting the target has a 1/2 chance of success.
                # Killed targets will be flagged for removal.
                elif msg["action"] == "shoot":
                    try:
                        roll = random.randint(1,20)
                        if roll >= 10:
                            output = f"BANG! {actor} has shot at {msg['target']}, and hit!"
                            flagged_actors.append((msg["target"], "killed"))
                            self.broadcast(output, block_duplicates=False)
                        else:
                            output = f"BANG! {actor} has shot at {msg['target']}, and missed!"
                            self.broadcast(output, block_duplicates=False)
                        
                    except Exception as e:
                        logging.warning(e)

            # outputs speak messages
            if speak_output:
                self.broadcast(speak_output)

                for actor in interrupted_actors:
                    self.send_to_actor(actor, f"You were interrupted by {speak_actor}!")

            # cleans up flagged actors
            for actor in flagged_actors:
                try:
                    self.actors[actor[0]]["conn"].close()
                    self.actors.pop(actor[0], None)

                    if actor[1] == "killed":
                        output = f"{actor[0]} has been killed!"
                    else:
                        output = f"{actor[0]} has left the room!"

                    self.broadcast(output)

                except Exception as e:
                    logging.warning(e)


            self.actors_lock.release()

            time.sleep(World.WAIT_TIME)

class Room():
    def __init__(self, name = "Mick's", description = "A western-style space saloon, right at the edge of the galaxy."):
        self.name = name
        self.description = description
        self.actors = []

    def dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "actors": self.actors
        }
    
    def add_actor(self, name):
        self.actors.append(name)

    def remove_actor(self, name):
        self.actors.pop(name, None)

    

if __name__ == "__main__":

    timestamp = datetime.now()

    logging.basicConfig(
        filename=f"logs/world {timestamp.strftime('%Y-%m-%d %H-%M-%S')}.log",  # Name of the log file
        level=logging.INFO,  # Minimum logging level to capture (e.g., INFO, DEBUG, WARNING, ERROR, CRITICAL)
        format='%(asctime)s - %(levelname)s - %(message)s'  # Format of log messages
    )

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING) 
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    parent_conn, child_conn = Pipe()
    world = World(child_conn)
    world.start()

    while True:
        msg = input()
        parent_conn.send(msg)
        if msg == "quit" or msg == "exit":
            break

    world.join()