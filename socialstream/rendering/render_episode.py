import json

import streamlit as st
from sotopia.database import AgentProfile, EnvironmentProfile, EpisodeLog
from sotopia.envs.parallel import render_text_for_agent, render_text_for_environment

from socialstream.rendering_utils import render_for_humans
from socialstream.utils import get_full_name, get_preview


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


def update_database_callback() -> None:
    pass


def rendering_demo() -> None:
    initialize_episodes_to_display()

    codenames = list(st.session_state.all_codenames.keys())

    def update() -> None:
        codename_key = st.session_state.selected_codename
        st.session_state.current_episodes = EpisodeLog.find(
            EpisodeLog.environment == st.session_state.all_codenames[codename_key]
        ).all()

    # Support customized database
    database_input = st.text_input(
        label="Use your own database (optional):",
        key="database_input",
        on_change=update_database_callback,
    )  # TODO check how to update the database

    # Dropdown for codename selection
    st.selectbox(
        "Choose a codename:",
        codenames,
        index=0,
        on_change=update,
        key="selected_codename",
    )

    selected_index = st.number_input(
        "Specify the index of the episode to display:",
        min_value=0,
        max_value=len(st.session_state.current_episodes) - 1,
        value=0,
        step=1,
    )

    if selected_index < len(st.session_state.current_episodes):
        # TODO unify the display function across render and chat
        episode = st.session_state.current_episodes[selected_index]
        agents = [AgentProfile.get(agent) for agent in episode.agents]
        agent_names = [get_full_name(agent) for agent in agents]
        environment = EnvironmentProfile.get(episode.environment)
        agent_goals = [
            render_text_for_agent(agent_goal, agent_id)
            for agent_id, agent_goal in enumerate(environment.agent_goals)
        ]

        avatar_mapping = {
            agent_names[0]: "👤",
            agent_names[1]: "🧑",
        }

        messages = render_for_humans(episode)

        background_messages = [
            message for message in messages if message["role"] == "Background Info"
        ]
        evaluation_messages = [
            message for message in messages if message["type"] == "comment"
        ]
        conversation_messages = [
            message
            for message in messages
            if message not in background_messages and message not in evaluation_messages
        ]

        assert (
            len(background_messages) == 2
        ), f"Need 2 background messages, but got {len(background_messages)}"
        st.markdown(
            f"**Scenario**: { render_text_for_environment(environment.scenario)}"
        )

        goal_col1, goal_col2 = st.columns(2)
        with goal_col1:
            with st.expander(f"**Agent 1 Goal:** {get_preview(agent_goals[0])}"):
                st.markdown(agent_goals[0])
        with goal_col2:
            with st.expander(f"**Agent 2 Goal:** {get_preview(agent_goals[1])}"):
                st.markdown(agent_goals[1])

        with st.expander("Conversation", expanded=True):
            for index, message in enumerate(conversation_messages):
                role = role_mapping.get(message["role"], message["role"])
                content = message["content"]

                if role == "obs" or message.get("type") == "action":
                    try:
                        content = json.loads(content)
                    except Exception as e:
                        print(e)

                with st.chat_message(
                    role, avatar=avatar_mapping.get(message["role"], None)
                ):
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
                        if role == agent_names[1]:
                            # add background grey color
                            st.write(f"**{role}**")
                            st.markdown(
                                f"""
                                <div style="background-color: lightgrey; padding: 10px; border-radius: 5px;">
                                    {content}
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        else:
                            st.write(f"**{role}**")
                            st.markdown(
                                content.replace("\n", "<br />"), unsafe_allow_html=True
                            )

        with st.expander("Evaluation Results", expanded=True):
            for message in evaluation_messages:
                st.markdown(
                    message["content"].replace("\n", "<br />"), unsafe_allow_html=True
                )
