from abc import ABC, abstractmethod
from llm import LLM, GPTMessage
import logging

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
    DEFAULT_LIMIT = 30
    DEFAULT_KEEP = 10


    def __init__(self, 
                 llm: LLM = None, 
                 context_limit = DEFAULT_LIMIT, 
                 context_keep = DEFAULT_KEEP, 
                 context: list[GPTMessage] = [], 
                 summary = "", 
                 logger: logging.Logger = None):
        self.llm = llm
        self.context = context
        self.context_limit = context_limit
        self.context_keep = context_keep
        self.summary = summary
        self.logger = logger

    def log(self, message):
        if self.logger:
            self.logger.info(message)

    def clear(self):
        self.context = []

    def trim(self):
        """
        Trims the context, keeping context_keep messagess
        """
        start = max(0, len(self.context) - self.context_keep)
        self.context = self.context[start:]

    def append(self, message: GPTMessage):
        """
        Appends a GPTMessage to the context
        """
        self.context.append(message)
        self.log(f"Appended message to context: {message}")

        if len(self.context) >= self.context_limit:
            self.log(f"Reached context window size {len(self.context)}/{self.context_limit}")
            self.on_limit_reached()

    @abstractmethod
    def on_limit_reached(self):
        """
        Method to run on hitting context_limit messages
        """
        pass

class SummaryContext(Context):
    """
    Context which summarizes and keeps a certain number of 

    Args:
        name (str): the name of the Actor
        personality (str): the personality of the Actor
        goal (str): the Actor's primary goal
        llm (LLM): the LLM to use when summmarizing
        context_limit (int): the point at which the message list gets pruned
        context_keep (int): the number of messages to keep upon pruning
        context (list[GPTMessage]): for pre-loading history
        summary (str): for pre-loading long-term memory
        logger (Logger): to log
    """
    def __init__(self, 
                 name: str,
                 personality: str,
                 goal: str,
                 llm = None, 
                 context_limit=Context.DEFAULT_LIMIT, 
                 context_keep=Context.DEFAULT_KEEP, 
                 context=[], 
                 summary="", 
                 logger = None):
        super().__init__(llm, context_limit, context_keep, context, summary, logger)
        self.name = name
        self.personality = personality
        self.goal = goal

    def summarize(self):
        """
        Summarizes the context using the LLM.
        """
        summary_message = [{"role": "developer", "content": f"""You are {self.name}.
        Your personality is: {self.personality}
        Your primary goal is: {self.goal}

        Your long-term memory is:
        {self.summary}

        Your short-term memory will follow as a sequence of messages."""}]

        prompt = summary_message + self.context + [{"role": "developer", "content":
            """Update your long-term memory by summarizing your short-term memory, while keeping your last summary within your long-term memory in mind. 
            
            Make note of:
            - Other characters, when and where they've left or died, and what you think of them.
            - Steps you plan to take in the near future.
            
            Keep your summary in first-person."""}]
        
        response = self.llm.prompt(prompt)
        self.summary = response.output_text
        

        self.log(f"Created a summary:\n{response.output}")

    def on_limit_reached(self):
        """
        Summarizes, then trims context.
        """
        self.summarize()
        self.trim()