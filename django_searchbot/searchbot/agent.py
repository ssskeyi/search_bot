import os
import json
from typing import List, Dict, Any, Tuple, Optional
from langchain_community.tools.tavily_search import TavilySearchResults
import datetime
from openai import OpenAI
import time
from abc import ABC, abstractmethod

class SearchTool(ABC):
    """搜索工具抽象基类"""
    @abstractmethod
    def search(self, query: str) -> str:
        pass

class TavilySearchTool(SearchTool):
    """Tavily搜索工具实现"""
    def __init__(self):
        os.environ['TAVILY_API_KEY'] = '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'
        self.tavily = TavilySearchResults(max_results=5)
        self.tavily.description = '这是一个类似谷歌和百度的搜索引擎，搜索知识、天气、股票、电影、小说、百科等都是支持的。但是只支持英文输入的问题，会会返回5轮运行结果。'

    def search(self, query: str) -> str:
        try:
            return self.tavily.invoke(input=query)
        except Exception as e:
            return f"搜索出错: {str(e)}"

class LLMClient:
    """LLM客户端单例类"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
        return cls._instance

    def generate_response(self, messages: List[Dict[str, str]], temperature: float = 0, 
                         stop_words: List[str] = None) -> str:
        try:
            completion = self.client.chat.completions.create(
                model="qwen-plus",
                messages=messages,
                temperature=temperature,
                stop=stop_words or []
            )
            return completion.choices[0].message.content
        except Exception as e:
            return str(e)

class SearchAgent:
    """搜索代理类"""
    def __init__(self, search_tool: SearchTool):
        self.search_tool = search_tool
        self.llm_client = LLMClient()
        self.prompt_template = '''
        Today is {today}. 
        Considering our previous conversations:
        {chat_history}

        你是一个智能搜索助手，对于用户提问的问题，你应该使用以下工具进行搜索，然后返回你认为合理的一个或者几个答案和原文链接：
        {tool_descs}

        Use the following format:

        Question: 你必须回答的用户问题
        Thought: 你的思考过程
        Action: the action to take ({tool_names})
        Action Input: the input for the action
        Observation: the result of the action
        ... (this Thought/Action/Action Input/Observation can be repeated zero or more times)
        Thought: I now know the final answer
        Final Answer: the final answer to the original input question

        Begin!

        Question: {query}
        {agent_scratchpad}
        '''

    def _format_chat_history(self, history: List[Tuple[str, str]]) -> str:
        return '\n'.join([f'Question:{his[0]}\nAnswer:{his[1]}' for his in history])

    def _parse_llm_response(self, response: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """解析LLM响应"""
        thought_i = response.rfind('Thought:')
        final_answer_i = response.rfind('\nFinal Answer:')
        action_i = response.rfind('\nAction:')
        action_input_i = response.rfind('\nAction Input:')
        observation_i = response.rfind('\nObservation:')

        if final_answer_i != -1:
            return None, None, None, response[final_answer_i + len('\nFinal Answer:'):].strip()

        if not (thought_i < action_i < action_input_i):
            return None, None, None, None

        thought = response[thought_i + len('Thought:'):action_i].strip()
        action = response[action_i + len('\nAction:'):action_input_i].strip()
        action_input = response[action_input_i + len('\nAction Input:'):].strip()
        if observation_i != -1:
            action_input = action_input[:observation_i - action_input_i - len('\nAction Input:')].strip()

        return thought, action, action_input, None

    def execute(self, query: str, chat_history: List[Tuple[str, str]] = None) -> Tuple[bool, str, List[Tuple[str, str]]]:
        """执行搜索代理"""
        chat_history = chat_history or []
        agent_scratchpad = ''
        
        while True:
            # 准备提示词
            today = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            prompt = self.prompt_template.format(
                today=today,
                chat_history=self._format_chat_history(chat_history),
                tool_descs=self.search_tool.tavily.description,
                tool_names=self.search_tool.tavily.name,
                query=query,
                agent_scratchpad=agent_scratchpad
            )

            # 调用LLM
            print(f'\033[32m---等待LLM返回... ...\n{prompt}\n\033[0m', flush=True)
            start_time = time.time()
            response = self.llm_client.generate_response(
                messages=[{'role': 'system', 'content': 'You are a helpful assistant.'}, 
                         {'role': 'user', 'content': prompt}],
                stop_words=['Observation:']
            )
            print(f"********花费时间:{time.time()-start_time}......", flush=True)
            print(f'\033[34m---LLM返回---\n{response}\n---\033[34m', flush=True)

            # 解析响应
            thought, action, action_input, final_answer = self._parse_llm_response(response)
            
            # 如果有最终答案，返回结果
            if final_answer:
                chat_history.append((query, final_answer))
                return True, final_answer, chat_history

            # 如果解析失败，返回错误
            if thought is None:
                return False, 'LLM回复格式异常', chat_history

            # 执行搜索
            try:
                action_input = json.loads(action_input)
                observation = self.search_tool.search(json.dumps(action_input))
            except Exception as e:
                observation = f'搜索出错: {str(e)}'

            # 更新上下文
            agent_scratchpad = f'{agent_scratchpad}{response}Observation: {observation}\n'

class SearchAgentFactory:
    """搜索代理工厂类"""
    @staticmethod
    def create(search_tool_type: str = 'tavily') -> SearchAgent:
        if search_tool_type.lower() == 'tavily':
            return SearchAgent(TavilySearchTool())
        else:
            raise ValueError(f'不支持的搜索工具类型: {search_tool_type}')

def agent_execute(query: str, chat_history: List[Tuple[str, str]] = None) -> Tuple[bool, str, List[Tuple[str, str]]]:
    """代理执行函数的包装器"""
    agent = SearchAgentFactory.create('tavily')
    return agent.execute(query, chat_history)

def main():
    # 创建搜索代理
    agent = SearchAgentFactory.create('tavily')
    my_history = []

    # 交互式搜索
    while True:
        query = input('query: ')
        success, result, my_history = agent.execute(query, chat_history=my_history)
        my_history = my_history[-10:]  # 保留最近10条对话历史

if __name__ == '__main__':
    main()