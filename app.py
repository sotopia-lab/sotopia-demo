import os

import streamlit as st

from socialstream.chat import chat_demo_omniscient
from socialstream.rendering import rendering_demo
from socialstream.utils import initialize_session_state, reset_database


def update_database_callback() -> None:
    new_database_url = st.session_state.new_database_url
    updated_url = (
        new_database_url if new_database_url != "" else st.session_state.DEFAULT_DB_URL
    )
    try:
        reset_database(updated_url)
    except Exception as e:
        st.error(f"Error occurred while updating database: {e}, please try again.")

    st.session_state.current_database_url = updated_url
    initialize_session_state(force_reload=True)

    print("Updated DB URL: ", st.session_state.current_database_url)


st.set_page_config(page_title="SocialStream_Demo", page_icon="🧊", layout="wide")
DISPLAY_MODE = "Display Episodes"
CHAT_OMNISCIENT_MODE = "Chat with Model"
if "DEFAULT_DB_URL" not in st.session_state:
    st.session_state.DEFAULT_DB_URL = os.environ.get("REDIS_OM_URL", "")
    st.session_state.current_database_url = st.session_state.DEFAULT_DB_URL
    print("Default DB URL: ", st.session_state.DEFAULT_DB_URL)

# impl 1: use sidebar to update URL
new_database_url = st.sidebar.text_input(
    "Enter Database URL: (Optional, starting in redis://)",
    value="",
    on_change=update_database_callback,
    key="new_database_url",
)

# # impl 2: use query params in URL
# query_params = st.experimental_get_query_params()
# current_database_url = query_params.get('database', [''])[0]

# def get_actual_database_url() -> str:
#     return current_database_url or st.session_state.DEFAULT_DB_URL

# actual_database_url = get_actual_database_url()
# if st.session_state.current_database_url != actual_database_url:
#     st.session_state.current_database_url = actual_database_url
#     reset_database(actual_database_url)
#     initialize_session_state(force_reload=True)
#     print("Actual DB URL: ", actual_database_url)
#     st.rerun()

option = st.sidebar.radio("Function", (CHAT_OMNISCIENT_MODE, DISPLAY_MODE))
if option == DISPLAY_MODE:
    rendering_demo()
elif option == CHAT_OMNISCIENT_MODE:
    chat_demo_omniscient()
