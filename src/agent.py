from multiprocessing.connection import Client
from multiprocessing import Process
import time

ADDRESS = ("localhost", 6000)

class Agent(Process):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.conn = None

    def connect(self):
        while self.conn == None:
            try:    
                self.conn = Client(ADDRESS)
            except ConnectionRefusedError:
                time.sleep(1)    
        self.conn.send(self.name)

    def run(self):
        self.connect()

        while True:
            pass

if __name__ == "__main__":
    bob = Agent("Bob")

    bob.start()

    time.sleep(3)

    alice = Agent("Alice")
    alice.start()

    bob.join()
    alice.join()