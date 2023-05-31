class RelogioLamport:
    def __init__(self, num_processos):
        self.num_processos = num_processos
        self.vetor = [0] * num_processos

    def incrementar(self, processo):
        self.vetor[processo] += 1

    def ajustar(self, outro_relogio):
        for i in range(self.num_processos):
            self.vetor[i] = max(self.vetor[i], outro_relogio[i])

    def obter_relogio(self):
        return self.vetor.copy()

