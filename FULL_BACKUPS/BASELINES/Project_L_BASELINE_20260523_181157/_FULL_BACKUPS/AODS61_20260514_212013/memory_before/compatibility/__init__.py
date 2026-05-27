from orchestration.tegan_triage import build_tegan_triage_report

tests = [
    'I am overwhelmed and need help',
    'Can you check my emails',
    'Research this for me',
    'memory audit please',
    'I need help with finance and DVA'
]

for item in tests:
    print('')
    print('MESSAGE:', item)
    print(build_tegan_triage_report(item))
    print('-' * 60)

