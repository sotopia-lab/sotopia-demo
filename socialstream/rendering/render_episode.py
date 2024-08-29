import json

import streamlit as st
from sotopia.database import EnvironmentProfile, EpisodeLog

from socialstream.rendering_utils import render_for_humans


def initialize_episodes_to_display() -> None:
    if "all_codenames" not in st.session_state:
        codename_pk_mapping = {
            env.codename: env.pk for env in EnvironmentProfile.find().all()
        }
        st.session_state.all_codenames = codename_pk_mapping
        st.session_state.current_episodes = EpisodeLog.find(
            EpisodeLog.environment
            == codename_pk_mapping[list(codename_pk_mapping.keys())[0]]
        ).all()


role_mapping = {
    "Background Info": "background",
    "System": "info",
    "Environment": "env",
    "Observation": "obs",
    "General": "eval",
}


def rendering_demo() -> None:
    initialize_episodes_to_display()

    codenames = list(st.session_state.all_codenames.keys())

    def update() -> None:
        codename_key = st.session_state.selected_codename
        st.session_state.current_episodes = EpisodeLog.find(
            EpisodeLog.environment == st.session_state.all_codenames[codename_key]
        ).all()

    # Dropdown for codename selection
    st.selectbox(
        "Select a codename:",
        codenames,
        index=0,
        on_change=update,
        key="selected_codename",
    )

    selected_index = st.number_input(
        "Select an index:",
        min_value=0,
        max_value=len(st.session_state.current_episodes) - 1,
        value=0,
        step=1,
    )
    if selected_index < len(st.session_state.current_episodes):
        episode = st.session_state.current_episodes[selected_index]

        messages = render_for_humans(episode)

        for index, message in enumerate(messages):
            role = role_mapping.get(message["role"], message["role"])
            content = message["content"]

            if role == "obs" or message.get("type") == "action":
                try:
                    content = json.loads(content)
                except Exception as e:
                    print(e)

            with st.chat_message(role):
                if isinstance(content, dict):
                    st.json(content)
                elif role == "info":
                    st.markdown(
                        f"""
                        <div style="background-color: lightblue; padding: 10px; border-radius: 5px;">
                            {content}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.write(f"**{role}**")
                    st.markdown(content.replace("\n", "<br />"), unsafe_allow_html=True)
