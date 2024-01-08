from dataclasses import field
import json
import os
from typing import List
from pydantic import BaseModel
import streamlit as st
import time
import promptflow as pf
from promptflow.entities import AzureOpenAIConnection


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
PAGE_TITLE = "Prompt flow + Streamlit"

CHAT_FLOW_PATH = "flows/chat"
TITLE_FLOW_PATH = "flows/make_title"


class Message(BaseModel):
    role: str
    content: str


class ChatThreadHistory(BaseModel):
    title: str
    is_default: bool = True
    messages: List[Message] = []

    def __post_init__(self):
        self.messages = [Message(**m) for m in self.messages]

    def to_promptflow_format(self):
        """Converts chat history to a format that can be used by PromptFlow"""
        promptflow_format = []
        for i in range(len(self.messages)//2):
            input = self.messages[i*2]
            output = self.messages[i*2+1]
            promptflow_format.append({"inputs": {"question": input.content},
                                      "outputs": {"answer": output.content}})

        return json.dumps(promptflow_format)


def save_chat_history(chat_history: List[ChatThreadHistory]):
    with open("chat_history.jsonl", "w") as f:
        f.truncate()
        for ch in chat_history:
            f.write(json.dumps(ch.model_dump()) + "\n")


def restore_chat_history():
    with open("chat_history.jsonl", "r") as f:
        st.session_state.chat_history = [ChatThreadHistory(**json.loads(ch))
                                         for ch in f.readlines()]


st.set_page_config(page_title=PAGE_TITLE)

# Set up PromptFlow
connection = AzureOpenAIConnection(name="azure_open_ai_connection",
                                   api_key=OPENAI_API_KEY,
                                   api_base=OPENAI_API_BASE)
pf_client = pf.PFClient()
pf_client.connections.create_or_update(connection)

chat_flow = pf.load_flow(source=CHAT_FLOW_PATH)
chat_flow.context.streaming = True
title_flow = pf.load_flow(source=TITLE_FLOW_PATH)

# on first load, restore chat history from file
if "chat_history" not in st.session_state and \
        os.path.exists("chat_history.jsonl"):
    restore_chat_history()

st.title(PAGE_TITLE)

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history: List[ChatThreadHistory] = [
        ChatThreadHistory(title="New Chat")]

with st.sidebar:
    st.selectbox("Chat Selection",
                 key="chat_i",
                 options=reversed(range(len(st.session_state.chat_history))),
                 format_func=lambda i: st.session_state.chat_history[i].title)

    st.button("New chat",
              on_click=lambda: st.session_state.chat_history.append(
                  ChatThreadHistory(
                      title="New Chat")))

    def delete_chat():
        st.session_state.chat_history.pop(st.session_state.chat_i)
        if len(st.session_state.chat_history) == 0:
            st.session_state.chat_history.append(
                ChatThreadHistory(title="New Chat"))
        save_chat_history(st.session_state.chat_history)

    st.button("Delete chat", on_click=lambda: delete_chat())

chat = st.empty()

# Display chat messages from history on app rerun
for message in st.session_state.chat_history[st.session_state.chat_i].messages:
    with st.chat_message(message.role):
        st.markdown(message.content)

# Accept user input
if prompt := chat.chat_input("Type a message..."):
    # Add user message to chat history
    chat_history = st.session_state.chat_history
    chat_history[st.session_state.chat_i].messages.append(
        Message(role="user", content=prompt))
    st.session_state.chat_history = chat_history
    save_chat_history(chat_history)
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # Convert session state message to format
        messages = []

        result = chat_flow(
            question=prompt,
            chat_history=str(
                st.session_state.chat_history[
                    st.session_state.chat_i].to_promptflow_format()))

        # Stream of response
        for r in result["answer"]:
            full_response += r
            time.sleep(0.08)
            # Add a blinking cursor to simulate typing
            message_placeholder.markdown(full_response + "▌")
        message_placeholder.markdown(full_response)

    # Add assistant response to chat history
    chat_history[st.session_state.chat_i].messages.append(
        Message(role="assistant", content=full_response))
    st.session_state.chat_history = chat_history
    save_chat_history(chat_history)

    # If the first message is a question, use it to generate a title
    if chat_history[st.session_state.chat_i].is_default:
        title = title_flow(user_question=chat_history[
            st.session_state.chat_i].messages[0].content)["title"]
        chat_history[st.session_state.chat_i].title = title
        chat_history[
            st.session_state.chat_i].is_default = False
        st.session_state.chat_history = chat_history
        save_chat_history(chat_history)
        st.experimental_rerun()
 