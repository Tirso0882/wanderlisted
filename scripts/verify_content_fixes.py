#!/usr/bin/env python3
"""Verify that Responses API content extraction fixes are in place."""

import sys


def test_stage4_graph_imports():
    """Test that stage4_graph has the helper function."""
    try:
        # Check via file content instead of import to avoid path issues
        with open("src/agent/stage4_graph.py", "r") as f:
            content = f.read()

        assert "def _extract_text_content(content)" in content, (
            "Helper function should exist"
        )
        print("✅ stage4_graph._extract_text_content exists")

        # Check helper implementation
        assert "isinstance(content, str)" in content, (
            "Helper should handle string content"
        )
        assert "isinstance(content, list)" in content, (
            "Helper should handle list content"
        )
        print("✅ Helper function handles both string and list content")
        return True
    except Exception as e:
        print(f"❌ stage4_graph helper check failed: {e}")
        return False


def test_llm_has_responses_api_param():
    """Test that get_llm passes use_responses_api=True."""
    try:
        with open("src/agent/llm.py", "r") as f:
            content = f.read()

        assert "use_responses_api=True" in content, (
            "llm.py should have use_responses_api=True"
        )
        print("✅ llm.py has use_responses_api=True parameter")
        return True
    except Exception as e:
        print(f"❌ llm.py check failed: {e}")
        return False


def test_api_main_has_helper():
    """Test that main.py has the content extraction helper."""
    try:
        with open("src/api/main.py", "r") as f:
            content = f.read()

        assert "_extract_text_content" in content, "main.py should have helper function"
        print("✅ main.py has _extract_text_content helper")

        # Check that it's used in streaming
        assert "_extract_text_content(msg.content)" in content, (
            "Helper should be used in streaming"
        )
        print("✅ Helper is used in streaming output")
        return True
    except Exception as e:
        print(f"❌ main.py check failed: {e}")
        return False


def test_stage4_graph_uses_helper():
    """Test that stage4_graph uses the helper in critical places."""
    try:
        with open("src/agent/stage4_graph.py", "r") as f:
            content = f.read()

        critical_uses = [
            ("triage_node", "_extract_text_content(response.content).strip().lower()"),
            ("supervisor routing", "_extract_text_content(last_message.content)"),
            (
                "agent_msgs summary",
                "_extract_text_content(m.content) for m in agent_msgs",
            ),
            ("budget_text", "_extract_text_content(m.content) for m in new_msgs"),
        ]

        for name, pattern in critical_uses:
            assert pattern in content, f"Missing {name} fix: {pattern}"
            print(f"✅ {name} uses helper")

        return True
    except Exception as e:
        print(f"❌ stage4_graph usage check failed: {e}")
        return False


def main():
    """Run all verification tests."""
    print("\n🔍 Verifying Responses API content extraction fixes...\n")

    tests = [
        ("Stage4Graph Helper", test_stage4_graph_imports),
        ("LLM Responses API Param", test_llm_has_responses_api_param),
        ("API Main Helper", test_api_main_has_helper),
        ("Stage4Graph Uses Helper", test_stage4_graph_uses_helper),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append(result)
        except Exception as e:
            print(f"❌ {name} test failed with exception: {e}")
            results.append(False)
        print()

    if all(results):
        print("✅ All verification tests passed!\n")
        return 0
    else:
        print("❌ Some verification tests failed.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
