import os
import pandas as pd

DIRS = ["ss", "sw", "ws", "ww"]


for dir in DIRS:
    files = os.listdir(os.path.join("logs", dir))

    wolf_wins = 0
    village_wins = 0
    total_runs = 0

    wolf_tokens = []
    village_tokens = []

    num_phases = []

    wolf_hung = []
    village_hung = []

    seer_kills_night = []
    wolf_kills = []
    vil_kills_day = []

    for file in files:
        try:
            df = pd.read_csv(os.path.join("logs", dir, file))
            winner_declaration = df.loc[df["action"] == "declare_winner"]
            winner = winner_declaration['content'].squeeze()
            win_phase = winner_declaration['phase'].squeeze()

            if isinstance(winner, str):

                phase_count = df["phase_num"].max()
                num_phases.append(phase_count)

                day_vote_count = len(df.loc[(df["action"] == "declare_vote_result") & (df["phase"] == "day")])

                night_vote_count = len(df.loc[(df["action"] == "declare_vote_result") & (df["phase"] == "night")])


                wolf_actions = df.loc[((df["model"] == "llama3.1:8b") | (df["model"] == "llama4:16x17b")) & (df["role"] == "werewolf")]
                wolf_tokens += wolf_actions["total_tokens"].tolist()

                village_actions = df.loc[((df["model"] == "llama3.1:8b") | (df["model"] == "llama4:16x17b")) & ((df["role"] == "villager") | (df["role"] == "seer"))]
                village_tokens += village_actions["total_tokens"].tolist()

                wolf_votes = df.loc[(df["phase"] == "night") & (df["action"] == "declare_vote_result")]
                village_votes = df.loc[(df["phase"] == "day") & (df["action"] == "declare_vote_result")]
                #print(len(wolf_votes))

                wolf_hung.append((phase_count - night_vote_count) / phase_count)

                if win_phase == "night":
                    village_hung.append((phase_count - 1 - day_vote_count) / (phase_count - 1))
                else:
                    village_hung.append((phase_count - day_vote_count) / phase_count)

                try:
                    vil_kill_day = df.loc[((df["role"] == "villager") | (df["role"] == "seer")) & (df["action"] == "declare_vote_result") & (df["phase"] == "day")]
                    vil_kills_day.append(len(vil_kill_day) / day_vote_count)

                    wolf_kill = df.loc[(df["role"] == "werewolf") & (df["action"] == "declare_vote_result")]
                    wolf_kills.append(len(wolf_kill) / day_vote_count)
                except:
                    pass #division by zero errors happen here, just ignore them

                if winner == "werewolves":
                    wolf_wins += 1
                    total_runs += 1
                elif winner == "village":
                    village_wins += 1
                    total_runs += 1

        except Exception as e:
            print(f"error with file {file}: {e}")

        #print(f"{file} winner: {winner}")

    print("---------------")
    print(f"Wolf win rate ({dir}): {wolf_wins}/{total_runs} ({wolf_wins/total_runs})")
    print(f"Avg tokens (wolves): {sum(wolf_tokens) / len(wolf_tokens)}")
    print(f"Avg tokens (village): {sum(village_tokens) / len(village_tokens)}")
    print(f"Avg num phases: {sum(num_phases) / len(num_phases)}")
    print(f"Wolf hung: {sum(wolf_hung)/len(wolf_hung)}")
    print(f"Village hung: {sum(village_hung)/len(village_hung)}")
    print(f"Day wolf kills: {sum(wolf_kills)/len(wolf_kills)}")
    print(f"Day villager kills: {sum(vil_kills_day)/len(vil_kills_day)}")