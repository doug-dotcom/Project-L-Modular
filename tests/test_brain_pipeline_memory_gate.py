import ast
from pathlib import Path


def _load_should_store_memory():
    source_path = Path(__file__).resolve().parents[1] / "core" / "cognition" / "brain_pipeline.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    wanted = {"clean_content", "should_store_memory"}
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace["should_store_memory"]


def test_questions_do_not_pollute_long_term_memory():
    should_store_memory = _load_should_store_memory()
    assert should_store_memory("When did Luella get her braces off?") is False
    assert should_store_memory("How is Luella?") is False


def test_explicit_memory_instruction_is_preserved_even_as_question():
    should_store_memory = _load_should_store_memory()
    assert should_store_memory("Can you remember that Luella loves netball?") is True
    assert should_store_memory("Please mark today as the day Luella got her braces off") is True
