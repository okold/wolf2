import json
from ollama import chat
from openai import OpenAI
from pydantic import BaseModel

API_PATH = "api.json"

class BasicActionMessage(BaseModel):
    action: str
    content: str
    reason: str | None

class AdvancedActionMessage(BaseModel):
    action: str
    content: str | None
    target: str | None
    reason: str | None

# TODO: graceful exit on bad api.json file
class LLM:
    """
    An interface for an LLM. Can be local or openai.
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
            self.model = model



    # TODO: not dict, but Response return
    def prompt(self, message: str | dict | list[dict], enforce_model = None, think = True) -> dict:
        """
        Prompts the LLM.

        Args:
            message (GPTMessage | list[GPTMessage]): context/message to send to LLM
            json (bool): forces JSON output, default False
        """
        if think and self.model not in ["deepseek-r1:8b", "deepseek-r1:14b", "qwen3:8b", "qwen3:13b", "magistral"]:
            think = False
            reasoning = False

        try:
            if self.cloud:
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
                content = response.choices[0].message.content
                
                usage = response.usage

                # TODO: rework this
                tokens_in = 0
                tokens_out = 0
                eval_in = 0
                eval_out = 0


            else:
                if enforce_model:
                    response = chat(self.model, messages=message, think=False, format=enforce_model.model_json_schema())
                else:
                    response = chat(self.model, messages=message, think=False)

                content = response.message.content

                if think:
                    reasoning = response.message.thinking
                tokens_in = response.prompt_eval_count
                tokens_out = response.eval_count
                eval_in = response.prompt_eval_duration / 1_000_000
                eval_out = response.eval_duration / 1_000_000

            return content, reasoning, tokens_in, tokens_out, eval_in, eval_out
        except Exception as e:
            print(f"{e}\nmessage = {message}")

        return None

if __name__ == "__main__":
    llm = LLM()
    llm.prompt("Why is the sky blue?")