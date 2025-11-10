from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from app.utils.config import settings


def create_llm_model():
    return OpenAIChatModel(
        "deepseek-chat", provider=DeepSeekProvider(api_key=settings.DEEPSEEK_API_KEY)
    )


llm_model = create_llm_model()
