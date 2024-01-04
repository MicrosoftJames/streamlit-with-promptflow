import os
import streamlit as st
from urllib.parse import urlencode
import requests
import dotenv
dotenv.load_dotenv()

# Configuration
client_id = os.environ["CLIENT_ID"]
client_secret = os.environ["CLIENT_SECRET"]
redirect_uri = os.environ["REDIRECT_URI"]
scope = "openid"  # Asking for the user's email in addition to a unique ID
authorization_url = os.environ["AUTHORIZATION_URL"]
token_url = os.environ["TOKEN_URL"]
state = os.environ["STATE"]


def get_user_id(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get("https://api.github.com/user", headers=headers)
    return response.json()["login"]


def get_access_token(code):
    data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }

    response = requests.post(token_url, data=data)

    if response.ok:
        access_token = response.content.decode().split('&')[0].split('=')[1]
        if access_token == "bad_verification_code":
            st.error('Error while obtaining the ID token.')
            st.stop()

        return access_token

    else:
        st.error('Error while obtaining the ID token.')
        st.stop()


def handle_login():
    if 'user_id' not in st.session_state and "code" not in st.experimental_get_query_params():
        query_params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'state': state,
            'prompt': 'select_account',
            'access_type': 'offline'
        }

        login_button = f'<div style="display: flex; justify-content: center; align-items: center; height: 50vh;"><button style="background-color: #24292e; color: white; padding: 15px; border-radius: 5px; border: none; text-decoration: none; font-size: 24px; width: fit-content; box-sizing: border-box;" onclick="this.style.backgroundColor=\'#555555\'; this.style.boxShadow=\'inset 0 3px 5px rgba(0, 0, 0, 0.2)\';"><a href="{authorization_url}?{urlencode(query_params)}" target="_self" style="color: white; text-decoration: none;"><img src="https://github.com/fluidicon.png" alt="GitHub" width="24" height="24" style="vertical-align: middle; margin-right: 5px;"> Login with GitHub</a></button></div>'

        st.markdown(login_button, unsafe_allow_html=True)
        st.stop()

    # Handle the callback and exchange code for an ID token
    elif 'user_id' not in st.session_state:
        code = st.experimental_get_query_params()['code'][0]
        state_returned = st.experimental_get_query_params().get('state')[0]
        st.experimental_set_query_params()

        if state_returned != state:
            st.error("State parameter does not match")
            st.stop()

        # Exchange code for a token
        access_token = get_access_token(code)
        user_id = get_user_id(access_token)

        st.session_state['user_id'] = user_id


def handle_logout():
    st.experimental_set_query_params()
    st.session_state.clear()
