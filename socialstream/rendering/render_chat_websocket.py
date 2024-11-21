import asyncio
import json
from dataclasses import dataclass
from typing import Any, Optional

import requests
import streamlit as st
import websockets

from socialstream.rendering_utils import messageForRendering, render_messages
from socialstream.utils import get_abstract


def compose_agent_names(agent_dict: dict[Any]) -> str:
    return f"{agent_dict['first_name']} {agent_dict['last_name']}"


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


class WebSocketManager:
    def __init__(self, url: str):
        self.url = url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.url)
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    async def send_message(self, message: dict):
        if self.websocket:
            await self.websocket.send(json.dumps(message))
        else:
            print("No active websocket connection")

    async def receive_message(self):
        if not self.websocket:
            return None
        try:
            message = await self.websocket.recv()
            return json.loads(message)
        except websockets.exceptions.ConnectionClosed:
            return None
        except Exception as e:
            print(f"Error receiving message: {e}")
            return None

    async def start_simulation(self, scenario_id: str, agent_ids: list[str]):
        await self.send_message(
            {
                "type": "START_SIM",
                "data": {
                    "env_id": scenario_id,
                    "agent_ids": agent_ids,
                },
            }
        )

    async def stop_simulation(self):
        await self.send_message({"type": "FINISH_SIM", "data": ""})


def initialize_session_state():
    if "active" not in st.session_state:
        # Initialize base state
        st.session_state.scenarios = get_scenarios()
        st.session_state.agent_list_1, st.session_state.agent_list_2 = get_agents()

        # Use first items as default choices
        st.session_state.scenario_choice = list(st.session_state.scenarios.keys())[0]
        st.session_state.agent_choice_1 = list(st.session_state.agent_list_1.keys())[0]
        st.session_state.agent_choice_2 = list(st.session_state.agent_list_2.keys())[0]

        # Initialize websocket manager and message list
        st.session_state.messages = []
        st.session_state.websocket_manager = WebSocketManager(
            "ws://localhost:8800/ws/simulation?token=demo-token"
        )

        # Set initial active state
        st.session_state.active = False
        print("Session state initialized")


def chat_demo():
    initialize_session_state()

    # Setup UI
    with st.container():
        # Scenario and Agent Selection
        with st.expander("Simulation Setup", expanded=True):
            scenario_col, scenario_desc_col = st.columns(2)
            with scenario_col:
                st.selectbox(
                    "Choose a scenario:",
                    st.session_state.scenarios.keys(),
                    key="scenario_choice",
                    disabled=st.session_state.active,
                )

            with scenario_desc_col:
                st.markdown(
                    f"""**Description:** {get_abstract(st.session_state.scenarios[st.session_state.scenario_choice]["scenario"])}""",
                    unsafe_allow_html=True,
                )

            st.selectbox(
                "Choose Agent 1:",
                st.session_state.agent_list_1.keys(),
                key="agent_choice_1",
                disabled=st.session_state.active,
            )
            st.selectbox(
                "Choose Agent 2:",
                st.session_state.agent_list_2.keys(),
                key="agent_choice_2",
                disabled=st.session_state.active,
            )

        # Control Buttons
        col1, col2, col3 = st.columns([1, 1, 3])

        def set_active(value: bool):
            st.session_state.active = value

        chat_history_container = st.empty()

        async def run_simulation():
            try:
                # Connect
                await st.session_state.websocket_manager.connect()

                # Start simulation
                await st.session_state.websocket_manager.start_simulation(
                    st.session_state.scenarios[st.session_state.scenario_choice]["pk"],
                    [
                        st.session_state.agent_list_1[st.session_state.agent_choice_1][
                            "pk"
                        ],
                        st.session_state.agent_list_2[st.session_state.agent_choice_2][
                            "pk"
                        ],
                    ],
                )

                while st.session_state.active:
                    message = await st.session_state.websocket_manager.receive_message()
                    if message is None:
                        continue
                    print("Received message", message)

                    if message["type"] == "END_SIM":
                        set_active(False)
                        break

                    if message["type"] == "SERVER_MSG":
                        st.session_state.messages.append(
                            messageForRendering(
                                role=message["data"]["role"],
                                content=message["data"]["content"],
                                type=message["data"]["type"],
                            )
                        )

                        with chat_history_container.container():
                            streamlit_rendering(
                                messages=st.session_state.messages,
                                agent_names=[
                                    st.session_state.agent_choice_1,
                                    st.session_state.agent_choice_2,
                                ],
                            )

                    if st.session_state.stop_sim:
                        print("Stopping simulation")
                        await st.session_state.websocket_manager.stop_simulation()
                        st.session_state.stop_sim = False

            finally:
                await st.session_state.websocket_manager.disconnect()

        def start_callback():
            if st.session_state.agent_choice_1 == st.session_state.agent_choice_2:
                st.error("Please select different agents")
            else:
                st.session_state.active = True
                st.session_state.stop_sim = False
                st.session_state.messages = []

        def stop_callback():
            st.session_state.stop_sim = True

        with col1:
            st.button(
                "Start Simulation",
                disabled=st.session_state.active,
                on_click=start_callback,
            )

        with col2:
            st.button(
                "Stop Simulation",
                disabled=not st.session_state.active,
                on_click=stop_callback,
            )

        if st.session_state.active:
            asyncio.run(run_simulation())
            st.rerun()

        with chat_history_container.container():
            streamlit_rendering(
                messages=st.session_state.messages,
                agent_names=[
                    st.session_state.agent_choice_1,
                    st.session_state.agent_choice_2,
                ],
            )


def streamlit_rendering(messages: list[messageForRendering], agent_names) -> None:
    agent1_name, agent2_name = agent_names
    avatar_mapping = {
        "env": "🌍",
        "obs": "🌍",
    }

    agent_names = [agent1_name, agent2_name]
    avatar_mapping = {agent_name: "🤖" for idx, agent_name in enumerate(agent_names)}
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
                print("Error in parsing JSON content", e)
                print("Content:", content)

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
