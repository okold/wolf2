import sys
from datetime import datetime
import os
import csv

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
from utils import CSVLogger

LOG_HEADERS = ["timestamp", "phase", "phase_num", "actor", "role", "strategy", "action", "target", "model", "context_length", "tokens_in", "tokens_out", "total_tokens", "eval_in (s)", "eval_out (s)", "eval_total (s)", "content", "prompt"]

class WolfLogger(CSVLogger):
    def __init__(self, experiment, seed = 1234):
        super().__init__(seed, f"{experiment}", "logs", LOG_HEADERS)
    
    def log(self, actor = "", action = "", content =  "", target = "", phase = "", phase_num = "", model="", tokens_in = 0, tokens_out = 0, eval_in = 0, eval_out = 0, strategy="", role="", prompt="", context_length = 0):
        with self.lock:
            with open(self.filepath, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writerow({"timestamp": datetime.now(),
                                 "actor": actor, 
                                 "action": action, 
                                 "content": content, 
                                 "target": target, 
                                 "phase": phase, 
                                 "phase_num": phase_num,
                                 "tokens_in": tokens_in,
                                 "tokens_out": tokens_out,
                                 "total_tokens": tokens_in + tokens_out,
                                 "eval_in (s)": eval_in, 
                                 "eval_out (s)": eval_out,
                                 "eval_total (s)": eval_in + eval_out,
                                 "model": model,
                                 "strategy": strategy,
                                 "role": role,
                                 "prompt": prompt,
                                 "context_length": context_length})