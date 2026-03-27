from abc import ABC, abstractmethod

class BaseAIProvider(ABC):
    @abstractmethod
    def list_models(self) -> list:
        """Fetch models from the API and return a standardized list of dicts."""
        pass

    @abstractmethod
    def generate_content(self, contents: str, config: dict = None) -> str:
        """Standard method for generating text."""
        pass

