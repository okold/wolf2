from abc import ABC, abstractmethod
from llm import LLM
from logging import Logger

from pydantic import BaseModel

class Context(ABC):
    """
    Abstract class for an LLM context.

    Args:
        llm (LLM): the LLM to use when summmarizing
        context_limit (int): the point at which the message list gets pruned
        context_keep (int): the number of messages to keep upon pruning
        context (list[GPTMessage]: for pre-loading history
        summary (str): for pre-loading long-term memory
        logger (Logger): to log
    """
    DEFAULT_LIMIT = 100
    DEFAULT_KEEP = 10


    def __init__(self, 
                 llm: LLM = None, 
                 context_limit = DEFAULT_LIMIT, 
                 context_keep = DEFAULT_KEEP, 
                 context: list[dict] = [],
                 logger: Logger = None,
                 csv_logger = None):
        self.llm = llm
        self.context = context
        self.context_limit = context_limit
        self.context_keep = context_keep
        self.logger = logger
        self.csv_logger = csv_logger

    def clear(self):
        self.context = []

    def trim(self):
        """
        Trims the context, keeping context_keep messagess
        """
        start = max(0, len(self.context) - self.context_keep)
        self.context = self.context[start:]

    def compress_context(self):

        compresed = []
        current_message = ""
        for message in self.context:
            if message["role"] == "user":
                if current_message != "":
                    current_message += "\n"
                current_message += f"{message['content']}"
            else:
                if current_message != "":
                    compresed.append({"role": "user", "content": current_message})
                    compresed.append(message)
                current_message = ""

        if current_message != "":
            compresed.append({"role":"user","content": current_message})

        return compresed

    def append(self, message: dict):
        """
        Appends a GPTMessage to the context
        """
        self.context.append(message)
        if isinstance(self.logger, Logger):
            self.logger.info(f"Appended message to context: {message}")

        if len(self.context) >= self.context_limit:
            if isinstance(self.logger, Logger):
                self.logger.info(f"Reached context window size {len(self.context)}/{self.context_limit}")
            self.on_limit_reached()

    @abstractmethod
    def on_limit_reached(self):
        """
        Method to run on hitting context_limit messages
        """
        pass

class SummaryContext(Context):
    """
    Context which summarizes on demand, with no limit
    """
    def __init__(self, 
                 name: str,
                 personality: str,
                 goal: str,
                 llm = None,
                 context=[],
                 summary="Your memories are fresh!",
                 logger = None,
                 csv_logger = None):
        super().__init__(llm=llm, context=context, logger=logger, csv_logger=csv_logger)
        self.name = name
        self.personality = personality
        self.goal = goal
        self.summary = summary

    def summarize(self, summary_message):
        """
        Summarizes the context using the LLM.
        """
        if self.context != []:

            prompt = [{"role": "system", "content": summary_message},
                      {"role": "user", "content": f"{self.compress_context()}"}]
            
            content, reasoning, tokens_in, tokens_out, eval_in, eval_out = self.llm.prompt(prompt)
            self.summary = content
            if isinstance(self.logger, Logger):
                self.logger.info(f"Created a summary. Usage: {tokens_in + tokens_out} ({eval_in + eval_out} ms)\n{reasoning}\n{self.summary}")
            self.csv_logger.log(actor=self.name, action="summarize", content=self.summary, tokens_in=tokens_in, tokens_out=tokens_out, eval_in=eval_in, eval_out=eval_out, prompt=prompt, context_length=len(prompt), strategy="summarize")

            self.context = []

    def on_limit_reached(self):
        """
        Summarizes, then trims context.
        """
        pass
        #self.summarize()
        #self.trim()

class WindowContext(Context):

    DEFAULT_LIMIT = 50

    def __init__(self, context_limit=DEFAULT_LIMIT, context = [], logger= None):
        super().__init__(context_limit=context_limit, context_keep=context_limit-1, context=context, logger=logger)

    def on_limit_reached(self):
        self.trim()