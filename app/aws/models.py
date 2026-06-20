"""
Here we create ollama model instances to replace AWS Bedrock models.

To use agents on AWS Bedrock, you would need AWS SDK for Python (boto3).
Strands uses boto3 to make calls to Amazon Bedrock.
You would need AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_SESSION_TOKEN.
Then you use a boto3 session and model id to create bedrock_model instance.
For more details check official docs:
https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/

Instead of that, we will use local Ollama server, providing local host and model id:
https://strandsagents.com/docs/user-guide/concepts/model-providers/ollama/

In this example app, we will use OllamaModel class instead BedrockModel.
We will use gemma4:e4b model.
Google specifically tuned Gemma 4 for function calling.
It provides the answer directly without the "According to the tool..." chatter.

Other tested models:
gemma2:9b does not support tools.
llama3.1:8b mentioned tool name in the answer.
qwen2.5:7b few times returned tool name and params instead results.
mistral:7b generates paragraph based on tool response, instead only providing information.
Gemma4:e4b is outperforming the 7B/8B models.
You can check available models on https://ollama.com/

Embedding models cannot be used for chat.
Instead, embedding models are used to generate semantic vectors that represent input in vector space.
We will use mxbai-embed-large:335m model.
Note that in AWS environment you would use boto3 library for semantic search.
"""

from functools import lru_cache
from ollama import Client
from strands.models.ollama import OllamaModel

gemma4_e4b_model = OllamaModel(
    host="http://localhost:11434",
    model_id="gemma4:e4b",
)


"""
While not strictly OllamaModel, method getEmbeddings uses embeding model from ollama,
therefore we will keep it here and call from agent tool or from migrations.
"""

ollamaClient = Client(host='http://localhost:11434')
embedModel = "mxbai-embed-large:335m"

@lru_cache(maxsize=128)
def getEmbeddings(description: str) -> list[float]:
    response = ollamaClient.embed(
        model=embedModel,
        input=description.lower(),
    )
    return response["embeddings"][0]
