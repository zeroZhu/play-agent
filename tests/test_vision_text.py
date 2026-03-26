from game_bot.vision import TextItem, VisionEngine


def test_find_text_partial_best_confidence():
    items = [
        TextItem(text="开始战斗", confidence=0.62, bbox=[[0, 0], [20, 0], [20, 10], [0, 10]]),
        TextItem(text="开始", confidence=0.91, bbox=[[10, 10], [30, 10], [30, 20], [10, 20]]),
    ]
    result = VisionEngine.find_text_in_items(items, query="开始", exact=False, min_confidence=0.5)
    assert result.found is True
    assert result.text == "开始"
    assert result.center == (20, 15)


def test_find_text_exact_miss():
    items = [
        TextItem(text="开始战斗", confidence=0.95, bbox=[[0, 0], [20, 0], [20, 10], [0, 10]])
    ]
    result = VisionEngine.find_text_in_items(items, query="开始", exact=True, min_confidence=0.5)
    assert result.found is False
