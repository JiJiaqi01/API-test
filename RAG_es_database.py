from langchain_openai import ChatOpenAI, OpenAIEmbeddings,OpenAI
from os import environ, getenv, path
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from datetime import datetime
from elasticsearch import Elasticsearch
from langchain_elasticsearch import ElasticsearchStore

#running local using docker

OPENAI_BASE_URL="https://api.chatanywhere.com.cn/v1"
OPENAI_API_KEY="sk-AUnJk0FMih4MJp32GAyNzEQRi5KtVeiZlvRU6tROmaOAFvD9"
OPENAI_MODEL="gpt-3.5-turbo-0125"
OPENAI_EMBEDDING_MODEL="text-embedding-3-small"

#create openai_embedding
embeddings= OpenAIEmbeddings(openai_api_base=OPENAI_BASE_URL,
                             openai_api_key=OPENAI_API_KEY,
                             model=OPENAI_EMBEDDING_MODEL)

vectorstore = ElasticsearchStore(
    embedding=embeddings,
    index_name="langchain-demo",
    es_connection="jq.debian.typist.cc:9200"
)



#create a template for the chatbot
template = """You must only use information from the provided search results.
Use an unbiased and journalistic tone. Combine search results together into a coherent answer.
Do not repeat text. Cite search results using [\[number\]] notation.
Only cite the most relevant results that answer the question accurately.
Place these citations at the end of the sentence or paragraph that reference them - do not put them all at the end.
If different results refer to different entities within the same name, write separate answers for each entity.
If you want to cite multiple results for the same sentence, format it as [\[number1\]] [\[number2\]], split with space.
However, you should NEVER do this with the same number - if you want to cite number1 multiple times for a sentence, only do [\[number1\]] not [\[number1\]] [\[number1\]]

You should use bullet points in your answer for readability. Put citations where they apply rather than putting them all at the end.

Anything between the following context html blocks is retrieved from a knowledge bank, not part of the conversation with the user.

{context}

REMEMBER: If there is no relevant information within the context, don't try to make up an answer.
Anything between the preceding 'context' html blocks is retrieved from a knowledge bank, not part of the conversation with the user.
The current date is {current_date} in format year/month/day.

"""

#generate the prompt
prompt = PromptTemplate.from_template(template)


#this function is for generating answer using RAG. input is the user's question
def openai_rag(question):
    #use tavily as source
    #find the api-key
    tavily_api_key=getenv("TAVILY_API_KEY",'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')

    tavily = TavilyClient(api_key=tavily_api_key)
    #generate context
    context="<context>"
    #count for counting id
    count=1
    #add reference
    reference= "### Reference"+"\n"
    #add url list
    url_list=""

    #first use tavily to surf answer
    res=tavily.search(question)

    #use es to search using mmr(choose from mmr and similarity)
    res=vectorstore.search(question,"mmr")
    
    #res is a dictionary, get the results
    results=res['results']
    
    #use for loop to get every element in the results dict
    for item in results:
        content=item['content']
        line="\n"+f"""<doc id={count}> """+content+"</doc>"
        context=context+line
        reference_line="\n"+f"""- [[{count}] """+item['title']+f"""]({item['url']})"""
        reference=reference+reference_line
        url_line=f"""[\[{count}\]]: {item['url']}"""+"\n"
        url_list=url_list+url_line
        count=count+1
    
    #results is a list with several dictionary in each index
    current_time=datetime.now()
    cdate=str(current_time.year)+"/"+str(current_time.month)+"/"+str(current_time.day)

    #use Open AI as our model
    #此处直接使用openai中转点的api,如果后续有官方的api可调整变量
    llm=ChatOpenAI(base_url='https://api.chatanywhere.com.cn/v1',api_key='sk-AUnJk0FMih4MJp32GAyNzEQRi5KtVeiZlvRU6tROmaOAFvD9', model='gpt-3.5-turbo-0125')


    #create a llm_chain
    llm_chain = LLMChain(prompt=prompt, llm=llm)

    #use the chain to query a answer
    answer=llm_chain.invoke(
        {
            "current_date":cdate,
            "context": context
        }
    )


    ans=answer['text']

    final_answer=ans+"\n"+"\n"+"\n"+reference+"\n"+"\n"+"\n"+url_list
    return final_answer