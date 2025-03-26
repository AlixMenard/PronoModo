bo3 = [[3,2,1,0],
       [2,3,1,1],
       [1,1,3,2],
       [0,1,2,3]]

bo5 = [[5,4,3,1,0,0],
       [4,5,4,2,1,0],
       [3,4,5,3,2,1],
       [1,2,3,5,4,3],
       [0,1,2,4,5,4],
       [0,0,1,3,4,5]]

class Bet:
    def __init__(self, team1:str, team2:str, score1:int, score2:int):
        self.team1 = team1
        self.team2 = team2
        self.score1 = score1
        self.score2 = score2

    @property
    def bo(self):
        return max(self.score1, self.score2)*2-1

    @property
    def id(self):
        return self.score1 - self.score2

    def __add__(self, result):
        assert(self.bo == result.bo)
        match self.bo:
            case 1:
                return int(self.score1 == result.score1)
            case 3:
                if self.id > 0:
                    ind1 = 2 - self.id
                else:
                    ind1 = 1 - self.id
                if result.id > 0:
                    ind2 = 2 - result.id
                else:
                    ind2 = 1 - result.id
                return bo3[ind1][ind2]
            case 5:
                if self.id > 0:
                    ind1 = 3 - self.id
                else:
                    ind1 = 2 - self.id
                if result.id > 0:
                    ind2 = 3 - result.id
                else:
                    ind2 = 2 - result.id
                return bo5[ind1][ind2]

class Result:
    def __init__(self, team1:str, team2:str, score1:int, score2:int):
        self.team1 = team1
        self.team2 = team2
        self.score1 = score1
        self.score2 = score2

    @property
    def bo(self):
        return max(self.score1, self.score2)*2-1

    @property
    def id(self):
        return self.score1 - self.score2