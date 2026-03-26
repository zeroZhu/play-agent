from game_bot.coords import apply_random_offset, scale_point


def test_scale_point():
    assert scale_point((640, 360), (1280, 720), (1920, 1080)) == (960, 540)
    assert scale_point((100, 50), (1000, 500), (500, 250)) == (50, 25)


def test_random_offset_range():
    point = (100, 100)
    for _ in range(200):
        x, y = apply_random_offset(point, 5)
        assert 95 <= x <= 105
        assert 95 <= y <= 105
