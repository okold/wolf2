from actor import Actor
from multiprocessing import Pipe

class Player(Actor):
    def __init__(self, name, pipe):
        super().__init__(name, personality="player", goal="player")
        self.pipe = pipe

    def run(self):
        self.connect()

        try:
            while True:
                if self.pipe.poll():
                    msg = self.pipe.recv()

                    if msg == "quit" or msg == "leave" or msg == "exit":
                        dict = {"action": "leave"}
                    elif msg.startswith("shoot"):
                        split = msg.split(" ")
                        dict = {"action": "shoot", "target": split[1]}
                    else:
                        dict = {"action": "speak", "content": msg}
                    self.conn.send(dict)

                if self.conn.poll():
                    msg = self.conn.recv()
                    # print(msg)
        except EOFError:
            self.conn.close()
            self.pipe.close()
            pass

if __name__ == "__main__":

    name = input("Choose a name: ")
    parent_conn, child_conn = Pipe()
    player = Player(name, child_conn)
    player.start()

    while True:
        msg = input(">> ")
        parent_conn.send(msg)

        if msg == "quit" or msg == "leave" or msg == "exit":
            break

    player.join()
    parent_conn.close()
    child_conn.close()
