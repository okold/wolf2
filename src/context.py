from abc import ABC, abstractmethod
from llm import LLM
import logging

from pydantic import BaseModel

class Message(BaseModel):
    role: str
    content: str

class Context(ABC):
    """
    Abstract class for an LLM context.
    """
    DEFAULT_LIMIT = 30
    DEFAULT_KEEP = 10


    def __init__(self, 
                 llm: LLM = None, 
                 context_limit = DEFAULT_LIMIT, 
                 context_keep = DEFAULT_KEEP, 
                 context = [], 
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

    def trim(self):
        start = max(0, len(self.context) - self.context_keep)
        self.context = self.context[start:]

    def append(self, message: Message):
        self.context.append(message)
        self.log(f"Appended message to context: {message}")

        if len(self.context) >= self.context_limit:
            self.log(f"Reached context window size {len(self.context)}/{self.context_limit}")
            self.on_limit_reached()

    @abstractmethod
    def on_limit_reached(self):
        pass

class SummaryContext(Context):
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

    def summarize(self) -> int:
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
        self.summarize()
        self.trim()