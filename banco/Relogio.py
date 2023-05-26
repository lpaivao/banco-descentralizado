class RelogioLamport:
    def __init__(self):
        self.tempo = 0

    def tick(self):
        self.tempo += 1

    def atualizar_tempo(self, tempo_recebido):
        self.tempo = max(self.tempo, tempo_recebido) + 1

    def obter_tempo(self):
        return self.tempo
