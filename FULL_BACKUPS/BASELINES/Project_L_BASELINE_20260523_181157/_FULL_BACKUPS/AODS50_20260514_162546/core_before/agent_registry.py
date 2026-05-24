from agents.punt import PuntAgent
from core.spine import register_agent

def load_agents():

    punt = PuntAgent()

    register_agent("punt", punt)
