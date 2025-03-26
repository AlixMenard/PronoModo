import pytest

from bets import Bet, Result  # Import the classes from your file

@pytest.mark.parametrize("score1, score2, expected", [
    (0, 1, 1),
    (1, 0, 1),
    (0, 2, 3),
    (1, 2, 3),
    (2, 0, 3),
    (2, 1, 3),
    (0, 3, 5),
    (1, 3, 5),
    (2, 3, 5),
    (3, 0, 5),
    (3, 1, 5),
    (3, 2, 5),
])
def test_bet_bo(score1, score2, expected):
    bet = Bet("Team1", "Team2", score1, score2)
    assert bet.bo == expected

@pytest.mark.parametrize("score1, score2, expected", [
    (0, 1, 1),
    (1, 0, 1),
    (0, 2, 3),
    (1, 2, 3),
    (2, 0, 3),
    (2, 1, 3),
    (0, 3, 5),
    (1, 3, 5),
    (2, 3, 5),
    (3, 0, 5),
    (3, 1, 5),
    (3, 2, 5),
])
def test_result_bo(score1, score2, expected):
    result = Result("Team1", "Team2", score1, score2)
    assert result.bo == expected
