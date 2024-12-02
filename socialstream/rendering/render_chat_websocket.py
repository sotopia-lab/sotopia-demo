import asyncio
import json
import threading
import time
from dataclasses import dataclass
from queue import Queue
from typing import Any, Optional

import aiohttp
import requests
import streamlit as st
import websockets

from socialstream.rendering_utils import messageForRendering, render_messages
from socialstream.utils import get_abstract


def compose_agent_names(agent_dict: dict[Any]) -> str:
    return f"{agent_dict['first_name']} {agent_dict['last_name']}"


def get_scenarios():
    # use synchronous code to get the scenarios
    with requests.get("http://localhost:8000/scenarios") as resp:
        scenarios = resp.json()
    return {scenario["codename"]: scenario for scenario in scenarios}


def get_agents() -> tuple[dict[str, dict[Any]], dict[str, dict[Any]]]:
    # use synchronous code to get the agents
    with requests.get("http://localhost:8000/agents") as resp:
        agents = resp.json()
    return {compose_agent_names(agent): agent for agent in agents}, {
        compose_agent_names(agent): agent for agent in agents
    }


def get_models() -> dict[str, dict[Any]]:
    # use synchronous code to get the agents
    with requests.get("http://localhost:8000/models") as resp:
        models = resp.json()
    return {model: model for model in models}, {model: model for model in models}


def initialize_session_state():
    if "active" not in st.session_state:
        # Initialize base state
        st.session_state.scenarios = get_scenarios()
        st.session_state.agent_list_1, st.session_state.agent_list_2 = get_agents()
        st.session_state.agent_model_1, st.session_state.agent_model_2 = get_models()

        # Use first items as default choices
        st.session_state.scenario_choice = list(st.session_state.scenarios.keys())[0]
        st.session_state.agent_choice_1 = list(st.session_state.agent_list_1.keys())[0]
        st.session_state.agent_choice_2 = list(st.session_state.agent_list_2.keys())[0]
        st.session_state.agent1_model_choice = list(
            st.session_state.agent_model_1.keys()
        )[0]
        st.session_state.agent2_model_choice = list(
            st.session_state.agent_model_2.keys()
        )[0]

        # Initialize websocket manager and message list
        st.session_state.messages = []
        # Set initial active state
        st.session_state.active = False

        st.session_state.websocket_manager = WebSocketManager(
            "ws://localhost:8000/ws/simulation?token=demo-token"
        )
        print("Session state initialized")


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
                print("Error in parsing JSON content")
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


class WebSocketManager:
    def __init__(self, url: str):
        self.url = url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.message_queue: Queue = Queue()
        self.running: bool = False
        self.receive_queue: Queue = Queue()
        self._closed = threading.Event()

    def start(self):
        """Start the client in a separate thread"""
        self._closed.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run_event_loop)
        self.thread.start()

    # def stop(self):
    #     """Stop the client"""
    #     self.running = False
    #     self.thread.join()
    def stop(self):
        """Stop the client"""
        print("Stopping websocket manager...")
        self.running = False
        self._closed.wait(timeout=5.0)
        if self.thread.is_alive():
            print("Thread is still alive after stop")
        else:
            print("Thread has been closed")

    def send_message(self, message: str | dict[str, Any]):
        """Add a message to the queue to be sent"""
        if isinstance(message, dict):
            message = json.dumps(message)
        self.message_queue.put(message)

    def _run_event_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._connect())

    # async def _connect(self):
    #     """Connect to the WebSocket server and handle messages"""
    #     async with aiohttp.ClientSession() as session:
    #         async with session.ws_connect(self.url) as ws:
    #             self.websocket = ws

    #             # Start tasks for sending and receiving messages
    #             send_task = asyncio.create_task(self._send_messages())
    #             receive_task = asyncio.create_task(self._receive_messages())

    #             # Wait for both tasks to complete
    #             await asyncio.gather(send_task, receive_task)

    async def _connect(self):
        """Connect to the WebSocket server and handle messages"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.url) as ws:
                    self.websocket = ws

                    # Start tasks for sending and receiving messages
                    send_task = asyncio.create_task(self._send_messages())
                    receive_task = asyncio.create_task(self._receive_messages())

                    # Wait for both tasks to complete
                    try:
                        await asyncio.gather(send_task, receive_task)
                    except Exception as e:
                        print(f"Error in tasks: {e}")
                    finally:
                        send_task.cancel()
                        receive_task.cancel()
        finally:
            print("WebSocket connection closed")
            self._closed.set()

    async def _send_messages(self):
        """Send messages from the queue"""
        while self.running:
            if not self.message_queue.empty():
                message = self.message_queue.get()
                await self.websocket.send_str(message)
            await asyncio.sleep(0.1)  # Small delay to prevent busy waiting

    async def _receive_messages(self):
        """Receive and handle incoming messages"""
        while self.running:
            try:
                msg = await self.websocket.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(f"Received message: {msg.data}")
                    self.receive_queue.put(json.loads(msg.data))
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
            except Exception as e:
                print(f"Error receiving message: {e}")
                break


def set_active(value: bool):
    st.session_state.active = value


def handle_end(message: dict[str, Any]):
    set_active(False)
    st.session_state.websocket_manager.stop()


def handle_server_msg(message: dict[str, Any]):
    st.session_state.messages.append(
        messageForRendering(
            role=message["data"]["role"],
            content=message["data"]["content"],
            type=message["data"]["type"],
        )
    )


def handle_error_msg(message: dict[str, Any]):
    # TODO handle different error
    print("[!!] Error in message: ", message)
    st.error(f"Error in message: {message['data']['content']}")


def handle_message(message: dict[str, Any]):
    # "END_SIM", "SERVER_MSG", "ERROR",
    match message["type"]:
        case "END_SIM":
            st.session_state.websocket_manager.stop()
            st.rerun()
        case "SERVER_MSG":
            handle_server_msg(message)
        case "ERROR":
            handle_error_msg(message)
        case _:
            st.error(f"Unknown message type: {message['data']['type']}")


def start_callback():
    if st.session_state.agent_choice_1 == st.session_state.agent_choice_2:
        st.error("Please select different agents")
    else:
        st.session_state.active = True
        st.session_state.messages = []
        st.session_state.websocket_manager.start()
        st.session_state.websocket_manager.send_message(
            {
                "type": "START_SIM",
                "data": {
                    "env_id": st.session_state.scenarios[
                        st.session_state.scenario_choice
                    ]["pk"],
                    "agent_ids": [
                        st.session_state.agent_list_1[st.session_state.agent_choice_1][
                            "pk"
                        ],
                        st.session_state.agent_list_2[st.session_state.agent_choice_2][
                            "pk"
                        ],
                    ],
                    "agent_models": [
                        st.session_state.agent_model_1[
                            st.session_state.agent_model_choice_1
                        ],
                        st.session_state.agent_model_2[
                            st.session_state.agent_model_choice_2
                        ],
                    ],
                },
            }
        )


def stop_callback():
    st.session_state.stop_sim = True
    st.session_state.websocket_manager.send_message(
        {
            "type": "FINISH_SIM",
            "data": "",
        }
    )


def is_active() -> bool:
    return st.session_state.websocket_manager.running


def chat_demo():
    initialize_session_state()

    with st.sidebar:
        with st.container():
            # Scenario and Agent Selection
            with st.expander("Simulation Setup", expanded=True):
                scenario_col, scenario_desc_col = st.columns(2)
                with scenario_col:
                    st.selectbox(
                        "Choose a scenario:",
                        st.session_state.scenarios.keys(),
                        key="scenario_choice",
                        disabled=is_active(),
                    )

                with scenario_desc_col:
                    st.markdown(
                        f"""**Description:** {get_abstract(st.session_state.scenarios[st.session_state.scenario_choice]["scenario"])}""",
                        unsafe_allow_html=True,
                    )

                agent1_col, agent2_col = st.columns(2)
                with agent1_col:
                    st.selectbox(
                        "Choose Agent 1:",
                        st.session_state.agent_list_1.keys(),
                        key="agent_choice_1",
                        disabled=is_active(),
                    )

                with agent2_col:
                    st.selectbox(
                        "Choose Agent 2:",
                        st.session_state.agent_list_2.keys(),
                        key="agent_choice_2",
                        disabled=is_active(),
                    )

                model1_col, model2_col = st.columns(2)
                with model1_col:
                    st.selectbox(
                        "Choose Agent 1 Model:",
                        st.session_state.agent_model_1.keys(),
                        key="agent_model_choice_1",
                        disabled=is_active(),
                    )

                with model2_col:
                    st.selectbox(
                        "Choose Agent 2 Model:",
                        st.session_state.agent_model_2.keys(),
                        key="agent_model_choice_2",
                        disabled=is_active(),
                    )

        # Control Buttons
        col1, col2, col3 = st.columns([1, 1, 3])

        with col1:
            st.button(
                "Start Simulation",
                disabled=is_active(),
                on_click=start_callback,
            )

        with col2:
            st.button(
                "Stop Simulation",
                disabled=not is_active(),
                on_click=stop_callback,
            )

    chat_history_container = st.empty()
    while is_active():
        if (
            "websocket_manager" in st.session_state
            and st.session_state.websocket_manager.receive_queue.qsize() > 0
        ):
            # get messages one by one and process them

            while not st.session_state.websocket_manager.receive_queue.empty():
                message = st.session_state.websocket_manager.receive_queue.get()
                handle_message(message)

        with chat_history_container.container():
            streamlit_rendering(
                messages=st.session_state.messages,
                agent_names=list(st.session_state.agents.keys())[:2],
            )
        time.sleep(1)

    with chat_history_container.container():
        streamlit_rendering(
            messages=st.session_state.messages,
            agent_names=list(st.session_state.agents.keys())[:2],
        )


if __name__ == "__main__":
    chat_demo()
