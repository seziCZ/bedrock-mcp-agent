import json
import textwrap

from typing import Self
from mcp.types import PromptMessage, TextContent


class PromptBuilder:
    """
    A fluent builder for composing sequences of `PromptMessage` objects.
    This class provides convenient methods to add user, assistant, and system
    messages, and then build a final prompt structure suitable for LLM requests.
    """

    def __init__(
            self,
            max_tokens: int = 500,
            top_p: float = 0.9,
            top_k: int = 20,
            temperature: float = 0.7,
            prompts: list[PromptMessage] | None = None,
    ):
        """
        Initialize a new PromptBuilder instance.
        :param max_tokens: Maximum number of tokens to generate.
        :param top_p: Nucleus sampling parameter (probability mass cutoff).
        :param top_k: Limits sampling to the top-k most likely tokens.
        :param temperature: Sampling temperature for randomness control.
        :param prompts: Optional initial list of `PromptMessage` objects.
        """
        self._prompts = prompts or []
        self._inference_config = {
            "maxTokens": max_tokens,
            "topP": top_p,
            "topK": top_k,
            "temperature": temperature,
        }

    def add_prompt(self, role: str, text: str) -> Self:
        """
        Add a new prompt message to the builder.

        :param role: The role of the message (e.g., "user", "assistant", "system").
        :param text: The text content of the message.
        :return: The builder instance (for method chaining).
        """
        self._prompts.append(
            PromptMessage(
                role=role,
                content=TextContent(
                    type="text",
                    text=text
                )
            )
        )
        return self

    def add_user_prompt(self, text: str) -> Self:
        """
        Add a user message with the given text.
        :param text: Text content of the user’s message.
        :return: The builder instance (for method chaining).
        """
        self.add_prompt("user", text)
        return self

    def add_assistant_prompt(self, text: str) -> Self:
        """
        Add an assistant message with the given text.
        :param text: Text content of the assistant’s message.
        :return: The builder instance (for method chaining).
        """
        self.add_prompt("assistant", text)
        return self

    def add_system_prompt(self, text: str) -> Self:
        """
        Add a system-level message with the given text.
        :param text: Text content of the system message.
        :return: The builder instance (for method chaining).
        """
        self.add_prompt("system", text)
        return self

    def build(self) -> str:
        """
        Finalize and return the built prompt structure, ready to be sent to an LLM.
        :return: The assembled prompt data.
        """
        return json.dumps({
            "schemaVersion": "messages-v1",
            "inferenceConfig": self._inference_config,
            "system": [
                {
                    "text": textwrap.dedent("""
                        You are an assistant that always focuses on the user's most recent message and responds based 
                        solely on that prompt, including any previously stored or recalled contextual information 
                        **only if it is directly relevant** to the current query. Do not introduce unrelated facts, 
                        stories, or examples from memory, and avoid adding general knowledge or commentary unless it is 
                        necessary to answer the user’s specific request. All references to stored memory should be used
                         strictly to enrich the response in a way that is pertinent and helpful to the current message.
                    """)
                }
            ],
            "messages": [
                {
                    "role": prompt.role,
                    "content": [{prompt.content.type: prompt.content.text}],
                }
                for prompt in self._prompts
            ],
        })
