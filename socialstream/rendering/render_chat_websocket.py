import asyncio
import json
from typing import Any

import aiohttp
import streamlit as st
import websockets

from socialstream.rendering_utils import messageForRendering, render_messages
from socialstream.utils import get_abstract


def compose_agent_names(agent_dict: dict[Any]) -> str:
    return f"{agent_dict['first_name']} {agent_dict['last_name']}"


# async def get_scenarios():
#     async with aiohttp.ClientSession() as session:
#         async with session.get("http://localhost:8800/scenarios") as resp:
#             scenarios = await resp.json()
#     return {scenario["codename"]: scenario for scenario in scenarios}

# async def get_agents() -> tuple[dict[str, dict[Any]], dict[str, dict[Any]]]:
#     async with aiohttp.ClientSession() as session:
#         async with session.get("http://localhost:8800/agents") as resp:
#             agents = await resp.json()
#     return {compose_agent_names(agent): agent for agent in agents}, {compose_agent_names(agent): agent for agent in agents}

import requests


def get_scenarios():
    # use synchronous code to get the scenarios
    with requests.get("http://localhost:8800/scenarios") as resp:
        scenarios = resp.json()
    return {scenario["codename"]: scenario for scenario in scenarios}


def get_agents() -> tuple[dict[str, dict[Any]], dict[str, dict[Any]]]:
    # use synchronous code to get the agents
    with requests.get("http://localhost:8800/agents") as resp:
        agents = resp.json()
    return {compose_agent_names(agent): agent for agent in agents}, {
        compose_agent_names(agent): agent for agent in agents
    }


def initialize_session_state():
    if "active" not in st.session_state:
        st.session_state.scenarios = get_scenarios()
        st.session_state.agent_list_1, st.session_state.agent_list_2 = get_agents()
        # use the first item in the list as the default choice
        st.session_state.scenario_choice = list(st.session_state.scenarios.keys())[0]
        st.session_state.agent_choice_1 = list(st.session_state.agent_list_1.keys())[0]
        st.session_state.agent_choice_2 = list(st.session_state.agent_list_2.keys())[0]
        st.session_state.active = False
        st.session_state.messages = []

        print("Session state initialized")


def chat_demo() -> None:
    initialize_session_state()

    with st.container():
        with st.expander("Create your scenario!", expanded=True):
            scenario_col, scenario_desc_col = st.columns(2)
            with scenario_col:
                st.selectbox(
                    "Choose a scenario:",
                    st.session_state.scenarios.keys(),
                    disabled=st.session_state.active,
                    index=0,
                    key="scenario_choice",
                )

            with scenario_desc_col:
                st.markdown(
                    f"""**Scenario Description:** {get_abstract(st.session_state.scenarios[st.session_state.scenario_choice]["scenario"])}""",
                    unsafe_allow_html=True,
                )

            def agent_choice_callback():
                if st.session_state.agent_choice_1 == st.session_state.agent_choice_2:
                    st.warning("Please select different agents.")

            st.selectbox(
                "Choose Agent 1:",
                st.session_state.agent_list_1.keys(),
                disabled=st.session_state.active,
                index=0,
                on_change=agent_choice_callback,
                key="agent_choice_1",
            )
            st.selectbox(
                "Choose Agent 2:",
                st.session_state.agent_list_2.keys(),
                disabled=st.session_state.active,
                index=0,
                on_change=agent_choice_callback,
                key="agent_choice_2",
            )

        # Start simulation
        def start_simulation():
            st.session_state.active = True
            asyncio.run(run_simulation())

        st.button(
            "Start Simulation",
            on_click=start_simulation,
            disabled=st.session_state.active,
        )
        simulation_status_placeholder = st.empty()
        chat_history_container = st.empty()

        async def run_simulation():
            async with websockets.connect(
                "ws://localhost:8800/ws/simulation?token=demo-token"
            ) as websocket:
                await websocket.send(
                    json.dumps(
                        {
                            "type": "START_SIM",
                            "data": {
                                "env_id": st.session_state.scenarios[
                                    st.session_state.scenario_choice
                                ]["pk"],
                                "agent_ids": [
                                    st.session_state.agent_list_1[
                                        st.session_state.agent_choice_1
                                    ]["pk"],
                                    st.session_state.agent_list_2[
                                        st.session_state.agent_choice_2
                                    ]["pk"],
                                ],
                            },
                        }
                    )
                )

                while st.session_state.active:
                    msg = await websocket.recv()
                    msg_data = json.loads(msg)
                    print("Received message: ", msg_data)

                    if msg_data["type"] == "END_SIM":
                        st.session_state.active = False
                    elif msg_data["type"] == "SERVER_MSG":
                        message = messageForRendering(
                            role=msg_data["data"]["role"],
                            content=msg_data["data"]["content"],
                            type=msg_data["data"]["type"],
                        )
                        st.session_state.messages.append(message)

                        with chat_history_container.container():
                            streamlit_rendering(
                                st.session_state.messages,
                                agent_names=[
                                    st.session_state.agent_choice_1,
                                    st.session_state.agent_choice_2,
                                ],
                            )

        if st.session_state.active:
            simulation_status_placeholder.info("Simulation in progress...")

        with chat_history_container.container():
            streamlit_rendering(
                st.session_state.messages,
                agent_names=[
                    st.session_state.agent_choice_1,
                    st.session_state.agent_choice_2,
                ],
            )

        # if st.session_state.active:
        #     st.info("Simulation in progress...")
        #     st.experimental_rerun()


def streamlit_rendering(messages: list[messageForRendering], agent_names) -> None:
    agent1_name, agent2_name = agent_names
    avatar_mapping = {
        "env": "🌍",
        "obs": "🌍",
    }

    agent_names = [agent1_name, agent2_name]
    avatar_mapping = {
        agent_name: "🤖" for idx, agent_name in enumerate(agent_names)
    }  # TODO maybe change the avatar because all bot/human will cause confusion

    role_mapping = {
        "Background Info": "background",
        "System": "info",
        "Environment": "env",
        "Observation": "obs",
        "General": "eval",
        "Agent 1": agent1_name,
        "Agent 2": agent2_name,
        agent1_name: agent1_name,
        agent2_name: agent2_name,
    }

    for index, message in enumerate(messages):
        role = role_mapping.get(message["role"], "info")
        content = message["content"]

        if role == "background":
            continue

        if role == "obs" or message.get("type") == "action":
            try:
                content = json.loads(content)
            except Exception as e:
                print(e)

        with st.chat_message(role, avatar=avatar_mapping.get(role, None)):
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
            elif role in [agent1_name, agent2_name]:
                st.write(f"**{role}**")
                st.markdown(content.replace("\n", "<br />"), unsafe_allow_html=True)
            else:
                st.markdown(content.replace("\n", "<br />"), unsafe_allow_html=True)


if __name__ == "__main__":
    chat_demo()
