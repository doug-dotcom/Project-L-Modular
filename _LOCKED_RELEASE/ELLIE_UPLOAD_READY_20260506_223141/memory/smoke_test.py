from memory.sme import store_interaction, get_context, get_profile, proactive

print("== SME SMOKE TEST ==")
store_interaction("My name is Doug", "Nice to meet you")
store_interaction("I feel overwhelmed today", "Let's take one step")
print("Context:")
print(get_context("overwhelmed"))
print("Profile:", get_profile())
print("Proactive:", proactive())
