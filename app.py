import os

import streamlit as st
from sotopia.database import EpisodeLog

from socialstream.chat import chat_demo_omniscient
from socialstream.rendering import rendering_demo

DISPLAY_MODE = "Display Episodes"
CHAT_OMNISCIENT_MODE = "Chat with Model"

st.set_page_config(page_title="SocialStream_Demo", page_icon="🧊", layout="wide")


option = st.sidebar.radio("Function", (CHAT_OMNISCIENT_MODE, DISPLAY_MODE))
if option == DISPLAY_MODE:
    rendering_demo()
elif option == CHAT_OMNISCIENT_MODE:
    chat_demo_omniscient()
