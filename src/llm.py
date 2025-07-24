import json
from openai import OpenAI
from pydantic import BaseModel

API_PATH = "api.json"

class GPTMessage(BaseModel):
    role: str
    content: str

# TODO: graceful exit on bad api.json file
class LLM:
    """
    An interface for an LLM API. Currently only supports OpenAI. 
    
    Uses the Responses interface.

    By default, loads the model based on info from the "api.json" file in root.

    Args:
        model (Optional[str]): the name of the model to query
        api_key (Optional[str]): the key for the connection
    """
    def __init__(self, model: str = None, api_key: str = None):

        if not model or not api_key:
            json_file = open(API_PATH)
            api = json.load(json_file)
            json_file.close()
        else:
            api = {"model": model, "key": api_key}

        self.client = OpenAI(
            api_key=api["key"]
        )
        self.model = api["model"]

    # TODO: not dict, but Response return
    def prompt(self, message: str | GPTMessage | list[GPTMessage], json=False) -> dict:
        """
        Prompts the LLM.

        Args:
            message (GPTMessage | list[GPTMessage]): context/message to send to LLM
            json (bool): forces JSON output, default False
        """
        if json:
            response = self.client.responses.create(
                model = self.model,
                input=message,
                text = {"format": {"type": "json_object"}}
            )
        else:
            response = self.client.responses.create(
                model = self.model,
                input=message
            )

        return response

if __name__ == "__main__":
    llm = LLM()
    llm.prompt("Why is the sky blue?")