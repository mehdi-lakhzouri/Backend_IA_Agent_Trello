from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda
from typing import TypedDict

class MyState(TypedDict):
    name: str
    greeting: str

def greet(state: MyState) -> MyState:
    name = state.get("name", "inconnu")
    return {"name": name, "greeting": f"Bonjour {name}!"}

graph = StateGraph(MyState)
graph.add_node("greet", RunnableLambda(greet))
graph.set_entry_point("greet")
graph.set_finish_point("greet")  # ✅ ici

app = graph.compile()
result = app.invoke({"name": "Med"})
print(result["greeting"])  # Bonjour Med!
