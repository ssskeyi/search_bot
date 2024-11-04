import os
import json
from langchain_community.tools.tavily_search import TavilySearchResults
import datetime
from openai import OpenAI
import time

def llm(query, history=[], user_stop_words=[]):
    try:
        messages = [{'role': 'system', 'content': 'You are a helpful assistant.'}]
        for hist in history:
            messages.extend([{'role': 'user', 'content': hist[0]}, {'role': 'assistant', 'content': hist[1]}])
        messages.append({'role': 'user', 'content': query})
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=messages,
            temperature=0,
            stop=user_stop_words
        )
        return completion.choices[0].message.content
    except Exception as e:
        return str(e)
 
os.environ['TAVILY_API_KEY']='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'    # travily搜索引擎api key
tavily=TavilySearchResults(max_results=5)
tavily.description='这是一个类似谷歌和百度的搜索引擎，搜索知识、天气、股票、电影、小说、百科等都是支持的。但是只支持英文输入的问题，会会返回5轮运行结果。s'
tools=[tavily, ]
tool_names='or'.join([tool.name for tool in tools])
tool_descs=[]
for t in tools:
    args_desc=[]
    for name,info in t.args.items():
        args_desc.append({'name':name,'description':info['description'] if 'description' in info else '','type':info['type']})
    args_desc=json.dumps(args_desc,ensure_ascii=False)
    tool_descs.append('%s: %s,args: %s'%(t.name,t.description,args_desc))
tool_descs='\n'.join(tool_descs)

prompt_tpl='''

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

def agent_execute(query,chat_history=[]):
    global prompt_tpl, tools_1, tool_names, tool_descs, prompt_0, tools_0, tool_descs_0, tool_names_0
    
    agent_scratchpad=''
    while True:
        history='\n'.join(['Question:%s\nAnswer:%s'%(his[0],his[1]) for his in chat_history])
        today=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prompt=prompt_tpl.format(today=today,chat_history=history,tool_descs=tool_descs,tool_names=tool_names,query=query,agent_scratchpad=agent_scratchpad)
        print('\033[32m---等待LLM返回... ...\n%s\n\033[0m'%prompt,flush=True)
        start_time = time.time()
        response=llm(prompt,user_stop_words=['Observation:'])
        end_time = time.time()
        print("********花费时间:{}......".format(end_time-start_time), flush=True)
        print('\033[34m---LLM返回---\n%s\n---\033[34m'%response,flush=True)
        review_i = response.find('Review:')
        thought_i=response.rfind('Thought:')
        final_answer_i=response.rfind('\nFinal Answer:')
        action_i=response.rfind('\nAction:')
        action_input_i=response.rfind('\nAction Input:')
        observation_i=response.rfind('\nObservation:')
        if final_answer_i!=-1:
            final_answer=response[final_answer_i+len('\nFinal Answer:'):].strip()
            chat_history.append((query,final_answer))
            return True,final_answer,chat_history
        if not (thought_i<action_i<action_input_i):
            return False,'LLM回复格式异常',chat_history
        if observation_i==-1:
            observation_i=len(response)
            response=response+'Observation: '           
        review=response[review_i + len('Review:'):thought_i].strip()
        thought=response[thought_i+len('Thought:'):action_i].strip()
        action=response[action_i+len('\nAction:'):action_input_i].strip()
        action_input=response[action_input_i+len('\nAction Input:'):observation_i].strip()
        the_tool=None
        for t in tools:
            if t.name==action:
                the_tool=t
                break
        if the_tool is None:
            observation='the tool not exist'
            agent_scratchpad=agent_scratchpad+response+observation+'\n'
            continue 
        try:
            action_input=json.loads(action_input)
            tool_ret=the_tool.invoke(input=json.dumps(action_input))
        except Exception as e:
            observation='the tool has error:{}'.format(e)
        else:
            observation=str(tool_ret)            
        agent_scratchpad=agent_scratchpad+response+observation+'\n'

if __name__ == '__main__':
    my_history=[]
    while True:
        query=input('query:')
        success,result,my_history=agent_execute(query,chat_history=my_history)
        my_history=my_history[-10:]