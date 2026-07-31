from langchain.chat_models import init_chat_model

from app.conf.app_config import cfg

model_cfg = cfg.lm_config.models[cfg.lm_config.active]

llm = init_chat_model(
    model=model_cfg.model,
    model_provider="openai",
    api_key=model_cfg.api_key,
    base_url=model_cfg.base_url,
    temperature=0,
)


if __name__ == "__main__":
    for chunk in llm.stream("What is the meaning of life?"):
        print(chunk.text)
