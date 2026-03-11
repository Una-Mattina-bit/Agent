from langchain.agents import create_agent

from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location, get_user_id,
                                     get_current_month, fetch_external_data, fill_context_for_report)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from utils.user_context import reset_current_user_context, set_current_user_context

class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[rag_summarize, get_weather, get_user_location, get_user_id,
                   get_current_month, fetch_external_data, fill_context_for_report],
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def execute_stream(self, query, user_context=None):
        input_dict = {
            "messages": [
                {"role": "user", "content": query},
            ]
        }

        runtime_context = {
            "report": False,
            "user_context": user_context or {},
        }
        token = set_current_user_context(user_context or {})

        try:
            for chunk in self.agent.stream(input_dict, stream_mode="values", context=runtime_context):
                latest_message = chunk["messages"][-1]
                if latest_message.content:
                    yield latest_message.content.strip() + "\n"
        finally:
            reset_current_user_context(token)

if __name__ == '__main__':
    agent = ReactAgent()
    for chunk in agent.execute_stream("扫地机器人如何保养"):
        print(chunk, end="", flush=True)
