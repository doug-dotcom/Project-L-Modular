from short_term_classifier import classify_message

tests = [

    "I feel stressed about money",
    "Project L runtime cognition",
    "Family matters deeply",
    "Recovery meeting tonight",
    "I feel lost in identity"
]

for t in tests:

    result = classify_message(t)

    print("")
    print(f"INPUT: {t}")
    print(f"CLASSIFIED AS: {result}")

