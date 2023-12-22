<p align="center" style="background-color: transparent;">
  <img src="imgs/robot.png" alt="Robot Blocks" width="100%" height="auto" style="display: block; margin-left: auto; margin-right: auto; width: 50%;">
</p>


# Streamlit with Prompt flow Demo
This project demonstrates how to use [Streamlit](https://streamlit.io/) to build a simple chat app that uses [Prompt flow](https://microsoft.github.io/promptflow) to generate responses with a model deployed in Azure OpenAI Service. The app uses two flows:
1. [chat](flows/chat) - for generating responses to user input given the context of the conversation
2. [make_title](flows/make_title/) - for generating a title for a conversation using the initial user question

# Install dependencies
You can install the dependencies using pip:
```bash
pip install -r requirements.txt
```

# Environment variables
You must set the following environment variables:
- `OPENAI_API_KEY` - The API key for your Azure OpenAI Service resource
- `OPENAI_API_BASE` - The base URL for your Azure OpenAI Service resource in the form `https://<resource-name>.openai.azure.com`