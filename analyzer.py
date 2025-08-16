import csv

import pandas as pd



FILE = "logs/20250811213822 sw.csv"
df = pd.read_csv(FILE)

print("LYNCHINGS:")

vote_declarations = df.loc[df["action"] == "declare_vote_result"]
print(vote_declarations[['phase', 'phase_num', 'target', 'role']])

print("VOTES:")

votes = df.loc[df["action"] == "vote"]
print(votes[['phase', 'phase_num', 'actor', 'role', 'target']])

print("WINNER:")

winner_declaration = df.loc[df["action"] == "declare_winner"]
print(winner_declaration['content'])