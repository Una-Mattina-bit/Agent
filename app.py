import time

import streamlit as st
from utils.runtime_checks import validate_runtime_environment
from utils.user_context import resolve_user_context

# 标题
st.title("智扫通机器人智能客服")
st.divider()

runtime_status = validate_runtime_environment()

if "user_context" not in st.session_state:
    st.session_state["user_context"] = resolve_user_context(runtime_status["tool_mode"])

with st.sidebar:
    st.caption(f"工具模式：`{runtime_status['tool_mode']}`")
    if st.button("刷新用户上下文", use_container_width=True):
        st.session_state["user_context"] = resolve_user_context(runtime_status["tool_mode"])
        st.rerun()

    user_context = st.session_state["user_context"]
    st.caption("当前用户上下文")
    st.write(f"- user_id: `{user_context.get('user_id') or '未解析'}`")
    st.write(f"- city: `{user_context.get('city') or '未解析'}`")
    st.write(f"- authenticated: `{user_context.get('authenticated', False)}`")
    st.write(f"- location_source: `{user_context.get('location_source', 'unknown')}`")
    if user_context.get("notes"):
        with st.expander("用户上下文说明", expanded=False):
            for note in user_context["notes"]:
                st.write(f"- {note}")

    if runtime_status["warnings"]:
        with st.expander("运行检查警告", expanded=False):
            for warning in runtime_status["warnings"]:
                st.write(f"- {warning}")

if runtime_status["errors"]:
    st.error("启动前检查未通过，请先修复以下问题：")
    for error in runtime_status["errors"]:
        st.write(f"- {error}")
    st.stop()

from agent.react_agent import ReactAgent

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

if "message" not in st.session_state:
    st.session_state["message"] = []

for message in st.session_state["message"]:
    st.chat_message(message["role"]).write(message["content"])

# 用户输入提示词
prompt = st.chat_input()

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})

    response_messages = []
    with st.spinner("智能客服思考中..."):
        res_stream = st.session_state["agent"].execute_stream(
            prompt,
            user_context=st.session_state["user_context"],
        )

        def capture(generator, cache_list):

            for chunk in generator:
                cache_list.append(chunk)

                for char in chunk:
                    time.sleep(0.01)
                    yield char

        st.chat_message("assistant").write_stream(capture(res_stream, response_messages))
        st.session_state["message"].append({"role": "assistant", "content": response_messages[-1]})
        st.rerun()
