from agent import Agent
from multiprocessing import Pipe

class Player(Agent):
    def __init__(self, name, pipe):
        super().__init__(name)
        self.pipe = pipe

    def run(self):
        self.connect()

        while True:
            if self.pipe.poll():
                msg = self.pipe.recv()
                self.conn.send(msg)

            if self.conn.poll():
                msg = self.conn.recv()
                print(msg)

if __name__ == "__main__":

    print("Choose a name:")
    name = input()
    parent_conn, child_conn = Pipe()
    player = Player(name, child_conn)
    player.start()

    while True:
        print("Send a message to the server:")
        msg = input()
        parent_conn.send(msg)
