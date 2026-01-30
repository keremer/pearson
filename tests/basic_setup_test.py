"""
Basic test to verify the testing setup works.
"""
def test_basic_setup():
    """Test that pytest is working."""
    assert 1 + 1 == 2

def test_import_models():
    """Test that models can be imported."""
    from shared.models import Course, Lesson
    assert Course is not None
    assert Lesson is not None