import json
from openai import OpenAI
from pydantic import BaseModel

API_PATH = "api.json"

class BasicActionMessage(BaseModel):
    vote: str | None
    speech: str | None

class AdvancedActionMessage(BaseModel):
    action: str
    content: str | None
    target: str | None
    speech: str | None

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
    def __init__(self, cloud = False, model = "dolphin3:8b"):

        self.cloud = cloud

        if cloud:
            json_file = open(API_PATH)
            api = json.load(json_file)
            json_file.close()

            self.client = OpenAI(
                api_key=api["key"]
            )
            self.model = api["model"]
        else:
            self.client = OpenAI(
            base_url = 'http://localhost:11434/v1',
            api_key='ollama'
            )
            self.model = model



    # TODO: not dict, but Response return
    def prompt(self, message: str | dict | list[dict], enforce_model = None) -> dict:
        """
        Prompts the LLM.

        Args:
            message (GPTMessage | list[GPTMessage]): context/message to send to LLM
            json (bool): forces JSON output, default False
        """

        try:
            if enforce_model:
                response = self.client.chat.completions.parse(
                    model = self.model,
                    messages=message,
                    response_format=enforce_model
                )
            else:
                response = self.client.chat.completions.create(
                    model = self.model,
                    messages=message
                )

            return response
        except Exception as e:
            print(f"{e}\nmessage = {message}")

        return None

if __name__ == "__main__":
    llm = LLM()
    llm.prompt("Why is the sky blue?")