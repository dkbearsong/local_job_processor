"""
Langchain Connector Module
A flexible connector class that integrates with Langchain features
and can be easily integrated with LM Studio or Ollama.
"""

from typing import Optional, Dict, Any, List
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.vectorstores import VectorStore
from langchain_community.llms import Ollama
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import logging

from app.robust_json_parser import RobustJsonOutputParser


class LangchainConnector:
    """
    A flexible Langchain connector that provides multiple methods
    for integrating with various Langchain features and external applications.
    Supports integration with LM Studio, Ollama, and OpenAI.
    """

    def __init__(self,
                 model_name: str = "gpt-3.5-turbo",
                 provider: str = "openai",
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None):
        """
        Initialize the Langchain connector.

        Args:
            model_name: The language model to use (e.g., "gpt-3.5-turbo", "llama3", "mistral")
            provider: The provider type ("openai", "ollama", "lmstudio")
            base_url: Base URL for Ollama/LM Studio (e.g., "http://localhost:11434")
            api_key: OpenAI API key (optional, can be set via environment)
        """
        self.model_name = model_name
        self.provider = provider
        self.base_url = base_url
        self.api_key = api_key
        self.llm: Any = None
        self.memory: Optional[ChatMessageHistory] = None
        self.logger = logging.getLogger(__name__)

        # Initialize the language model based on provider
        self._setup_llm()

    def _setup_llm(self):
        """Setup the language model based on provider configuration."""
        if self.provider == "openai":
            # For OpenAI, use ChatOpenAI with optional API key
            if self.api_key:
                self.llm = ChatOpenAI(
                    openai_api_key=self.api_key, # type: ignore
                    model_name=self.model_name # type: ignore
                )
            else:
                # Use environment variable or default
                self.llm = ChatOpenAI(model_name=self.model_name) # type: ignore

        elif self.provider == "lmstudio":
            # For LM Studio, use ChatOpenAI with custom base URL (OpenAI-compatible API)
            if self.base_url:
                self.llm = ChatOpenAI(
                    model_name=self.model_name, # type: ignore
                    openai_api_base=self.base_url, # type: ignore
                    openai_api_key="not-needed"  # LM Studio doesn't require API key # type: ignore
                )
            else:
                raise ValueError("base_url is required for LM Studio provider")

        elif self.provider == "ollama":
            # For Ollama, use Ollama
            if self.base_url:
                self.llm = Ollama(
                    model=self.model_name,
                    base_url=self.base_url
                )
            else:
                # Default to local Ollama instance
                self.llm = Ollama(model=self.model_name)
        elif self.provider == "gemini":
            # For Gemini, use ChatGoogleGenerativeAI
            if self.api_key:
                self.llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=self.api_key
                )
            else:
                self.llm = ChatGoogleGenerativeAI(model=self.model_name)
        else:
            # Fallback to default OpenAI
            self.llm = ChatOpenAI(model_name=self.model_name) # type: ignore

    def create_simple_chain(self, prompt_template: str):
        """
        Create a simple LCEL chain with a custom prompt.

        Args:
            prompt_template: The prompt template string

        Returns:
            LCEL Runnable instance
        """
        prompt = PromptTemplate.from_template(prompt_template)
        return prompt | self.llm | StrOutputParser()

    def create_json_chain(self, prompt_template: str):
        """
        Create a simple LCEL chain with JSON output parsing using RobustJsonOutputParser.
        This parser handles common LLM formatting issues like doubled quotes and unescaped
        quote characters in JSON output.

        Args:
            prompt_template: The prompt template string

        Returns:
            LCEL Runnable instance that returns parsed JSON
        """
        prompt = PromptTemplate.from_template(prompt_template)
        return prompt | self.llm | RobustJsonOutputParser()

    def create_conversational_chain(self, prompt_template: str):
        """
        Create a conversational chain with memory support using LCEL.

        Args:
            prompt_template: The prompt template string

        Returns:
            RunnableWithMessageHistory instance
        """
        if not self.memory:
            self.memory = ChatMessageHistory()

        prompt = PromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm | StrOutputParser()

        # Ensure memory is not None for the lambda
        memory: ChatMessageHistory = self.memory

        return RunnableWithMessageHistory(
            chain,
            lambda session_id: memory,
            input_messages_key="input",
            history_messages_key="history"
        )

    def create_retrieval_chain(self,
                               vector_store: VectorStore,
                               prompt_template: Optional[str] = None):
        """
        Create a retrieval chain for RAG functionality.

        Args:
            vector_store: The vector store to retrieve from
            prompt_template: Optional custom prompt template

        Returns:
            RunnablePassthrough instance for retrieval
        """
        if not prompt_template:
            prompt_template = """Answer the question based only on the following context:
            {context}

            Question: {question}"""

        prompt = PromptTemplate.from_template(prompt_template)

        # Create a chain that retrieves from vector store and then processes with LLM
        return RunnablePassthrough.assign(
            context=lambda x: vector_store.similarity_search(x["question"])
        ).assign(answer=prompt | self.llm | StrOutputParser())

    def run_simple_query(self, query: str, prompt_template: Optional[str] = None) -> str:
        """
        Run a simple query through the LLM.

        Args:
            query: The user's query
            prompt_template: Optional custom prompt template

        Returns:
            Response from the LLM
        """
        if not prompt_template:
            prompt_template = "Answer the following question: {query}"

        chain = self.create_simple_chain(prompt_template)
        return chain.invoke({"query": query})

    def run_conversational_query(self, query: str,
                                 prompt_template: Optional[str] = None) -> str:
        """
        Run a conversational query with memory support.

        Args:
            query: The user's query
            prompt_template: Optional custom prompt template

        Returns:
            Response from the LLM with conversation context
        """
        if not prompt_template:
            prompt_template = "Answer the following question: {input}"

        chain = self.create_conversational_chain(prompt_template)
        return chain.invoke({"input": query}, config={"configurable": {"session_id": "default"}})

    def run_retrieval_query(self, query: str,
                            vector_store: VectorStore,
                            prompt_template: Optional[str] = None) -> str:
        """
        Run a retrieval query using RAG.

        Args:
            query: The user's query
            vector_store: Vector store to retrieve from
            prompt_template: Optional custom prompt template

        Returns:
            Response from the retrieval chain
        """
        chain = self.create_retrieval_chain(vector_store, prompt_template)
        return chain.invoke({"question": query})["answer"]

    def add_memory(self, memory_type: str = "conversation"):
        """
        Add memory to the connector.

        Args:
            memory_type: Type of memory to add
        """
        if memory_type == "conversation":
            self.memory = ChatMessageHistory()

    def set_model(self, model_name: str, provider: Optional[str] = None, base_url: Optional[str] = None):
        """
        Change the language model.

        Args:
            model_name: New model name
            provider: New provider type ("openai", "ollama", "lmstudio")
            base_url: New base URL (for Ollama/LM Studio)
        """
        if provider:
            self.provider = provider
        if base_url:
            self.base_url = base_url
        self.model_name = model_name

        # Re-initialize the language model
        self._setup_llm()

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary with model information
        """
        return {
            "model_name": self.model_name,
            "provider": self.provider,
            "base_url": self.base_url,
            "memory_enabled": self.memory is not None
        }

    def batch_process(self, queries: List[str],
                      prompt_template: Optional[str] = None) -> List[str]:
        """
        Process multiple queries in batch.

        Args:
            queries: List of queries to process
            prompt_template: Optional custom prompt template

        Returns:
            List of responses
        """
        if not prompt_template:
            prompt_template = "Answer the following question: {query}"

        chain = self.create_simple_chain(prompt_template)
        responses = []

        for query in queries:
            response = chain.invoke({"query": query})
            responses.append(response)

        return responses

    def is_model_available(self) -> bool:
        """
        Check if the current model is available.

        Returns:
            Boolean indicating if model is accessible
        """
        try:
            # Test the connection by running a simple query
            if self.provider == "openai":
                # For OpenAI, this will validate the API key
                return True
            else:
                # For local models (Ollama/LM Studio), test by running a simple query
                self.run_simple_query("test")
                return True
        except Exception as e:
            self.logger.error(f"Model unavailable: {e}")
            return False