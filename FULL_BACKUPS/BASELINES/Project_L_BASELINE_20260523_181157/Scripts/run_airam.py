from airam import run_airam

user_input = input("How are you feeling? ")

result = run_airam(user_input)

print("\nAIRAM RESPONSE:\n")

print(f"A — {result['A']}")
print(f"I — {result['I']}")
print(f"R — {result['R']}")
print(f"A — {result['A2']}")
print(f"M — {result['M']}")
