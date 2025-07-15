import json
from openai import OpenAI
from pydantic import BaseModel
import logging

class JSONMessage(BaseModel):
    action: str


### LLM
class LLM:
    def __init__(self):

        json_file = open("api.json")
        api = json.load(json_file)
        json_file.close()

        self.client = OpenAI(
            api_key=api["key"]
        )
        self.model = api["model"]

    def prompt(self, message, json=False):

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