import requests
import json
from threading import Semaphore
from flask import Flask, jsonify, request
import uuid
import datetime

user0 = {"id": 0, "nome": "Lucas", "tipo": "particular", "saldo": 400, "transacoes": {}}
user1 = {"id": 1, "nome": "Gabriela", "tipo": "particular", "saldo": 400, "transacoes": {}}
user2 = {"id": 2, "nome": "Lara", "tipo": "particular", "saldo": 400, "transacoes": {}}

contas = {"0": user0, "1": user1, "2": user2}


class Bank:
    def __init__(self, bank_id, host_flask, port_flask, accounts=None):
        if accounts is None:
            accounts = {}
        self.bank_id = bank_id
        self.host_flask = host_flask
        self.port_flask = port_flask

        # Semáforo para cada clientes
        self.clients_semaphore = {"0": Semaphore(1), "1": Semaphore(1), "2": Semaphore(1)}

        self.accounts = accounts
        self.contas_criadas = len(self.accounts)

        # Inicia o flask
        self.app = Flask(__name__)

        @self.app.route('/banco/conta', methods=['POST'])
        def create_account():
            # Extrai dados do corpo da requisição
            name = request.json.get('nome')
            account_type = request.json.get('tipo')

            # Cria uma nova conta com um ID único
            account_id = str(self.contas_criadas)
            account = {
                'id': account_id,
                'nome': name,
                'tipo': account_type,
                'saldo': 0,
                'transacoes': {}
            }

            # Adiciona a nova conta ao banco correspondente
            if account_id not in self.accounts:
                self.accounts[account_id] = account
                self.contas_criadas += 1
                # Cria o semáforo para o cliente correspondente
                self.clients_semaphore[account_id] = Semaphore(1)
                # Retorna o ID da nova conta criada
                return jsonify({'id': account_id}), 201  # Código de criado
            else:
                return jsonify({'Conflito': "Conta já existe"}), 409  # Código de conflito

        @self.app.route('/banco/conta/deposito', methods=['POST'])
        def deposit():
            # Extrai dados do corpo da requisição
            id = str(request.json.get('id'))
            deposito = request.json.get('deposito')

            # Adiciona o saldo a conta correspondente
            if id in self.accounts:
                with self.clients_semaphore[id]:
                    saldo_antigo = self.accounts[id]["saldo"]
                    self.accounts[id]["saldo"] += deposito
                    return jsonify({'Saldo antigo': saldo_antigo, 'Saldo novo': self.accounts[id]["saldo"]}), 200
            else:
                return jsonify({'Erro': "Usuário não existe"}), 404

        @self.app.route('/banco/conta/<account_id>/saldo', methods=['GET'])
        def get_balance(account_id):
            # Verifica se a conta existe no banco
            if account_id in self.accounts:
                # Retorna o saldo da conta
                return jsonify({'saldo': self.accounts[account_id]['saldo']}), 200
            else:
                # Retorna um erro 404 (Not Found) se a conta não existir
                return jsonify({'error': 'Account not found'}), 404

        @self.app.route('/banco/transferencia', methods=['POST'])
        def transfer():
            # Extrai dados do corpo da requisição
            from_bank_id = request.json.get('from_bank_id')
            from_account_id = request.json.get('from_account_id')
            to_bank_id = request.json.get('to_bank_id')
            to_account_id = request.json.get('to_account_id')
            amount = request.json.get('amount')

            # Se a transferência for do banco que está gerenciando a transferência para ele mesmo
            if from_bank_id is self.bank_id and to_bank_id is self.bank_id:
                # Verifica se o ID de destino e remetente existem
                if str(from_account_id) in self.accounts and str(to_account_id) in self.accounts:
                    # Inicia os semáforos nas contas correspondetes
                    with self.clients_semaphore[str(from_account_id)], self.clients_semaphore[str(to_account_id)]:

                        # Gera um ID único crescente, baseado na hora atual e
                        # no endereço MAC do computador para a transação
                        transaction_id = str(uuid.uuid1())
                        # Inicia uma nova transação com status "pendente"
                        transaction = {
                            'id': transaction_id,
                            'date_time': str(datetime.datetime.now()),
                            'from_bank_id': from_bank_id,
                            'from_account_id': from_account_id,
                            'to_bank_id': to_bank_id,
                            'to_account_id': to_account_id,
                            'amount': amount,
                            'status': 'pending'
                        }

                        self.accounts[str(from_account_id)]["transacoes"][transaction_id] = transaction

                        # Verifica se o saldo irá ficar negativo
                        if self.accounts[str(from_account_id)]['saldo'] - amount >= 0:
                            self.accounts[str(from_account_id)]['saldo'] -= amount
                            self.accounts[str(to_account_id)]['saldo'] += amount

                            # Atualiza o status da transação para "concluída"
                            self.accounts[str(from_account_id)]["transacoes"][transaction_id]['status'] = 'completed'
                            # Cria a transação na conta que receber a transferência também
                            self.accounts[str(to_account_id)]["transacoes"][transaction_id] = \
                                self.accounts[str(from_account_id)]["transacoes"][transaction_id]

                            # Retorna um JSON com o ID da transação e o status
                            return jsonify({'id': transaction_id, 'status': transaction['status']}), 200

                        else:
                            # Atualiza o status da transação para "cancelada"
                            self.accounts[str(from_account_id)]["transacoes"][transaction_id]['status'] = 'canceled'

                            # Retorna um JSON com o ID da transação e o status
                            return jsonify({'error': 'Saldo insuficiente. Operação cancelada'}), 400
                else:
                    # Retorna um JSON indicando que o destinatário ou remetente não existe
                    return jsonify({'error': 'Uma das contas não existe. Operação cancelada'}), 400

            # Se a transferência for do banco que está gerenciando a transação para outro banco
            elif from_bank_id is self.bank_id and to_bank_id is not self.bank_id:

                body_check_user = {
                    'to_bank_id': to_bank_id,
                    'to_account_id': to_account_id,
                }

                # Verifica se as contas existem
                verificacao = self.verifica_existencia_conta(body_check_user, to_bank_id)
                if verificacao == 200 and str(from_account_id) in self.accounts:
                    # Ativa o semáforo da conta correspondente
                    with self.clients_semaphore[str(from_account_id)]:
                        # Gera um ID único crescente, baseado na hora atual e
                        # no endereço MAC do computador para a transação
                        transaction_id = str(uuid.uuid1())
                        # Inicia uma nova transação com status "pendente"
                        transaction = {
                            'id': transaction_id,
                            'date_time': str(datetime.datetime.now()),
                            'from_bank_id': from_bank_id,
                            'from_account_id': from_account_id,
                            'to_bank_id': to_bank_id,
                            'to_account_id': to_account_id,
                            'amount': amount,
                            'status': 'pending'
                        }

                        # Cria a transação pendente
                        self.accounts[str(from_account_id)]["transacoes"][transaction_id] = transaction

                        # Verifica se o saldo irá ficar positivo ou negativo
                        if self.accounts[str(from_account_id)]['saldo'] - amount >= 0:
                            # Retém temporariamente o dinheiro que vai ser transferido
                            self.accounts[str(from_account_id)]['saldo'] -= amount

                            # Tenta realizar a transferência
                            status = self.envia_transferencia_esse_para_outro(transaction, to_bank_id)

                            if status == 200:
                                try:
                                    # Se conseguir fazer a transferencia no outro banco, o valor retido é descontado
                                    # Atualiza o status da transação para "concluída"
                                    self.accounts[str(from_account_id)]["transacoes"][transaction_id][
                                        'status'] = 'completed'

                                    # Retorna um JSON com o ID da transação e o status
                                    return jsonify(
                                        {'transaction id': transaction_id, 'status': transaction['status']}), 200
                                except Exception as e:
                                    # Retorna um JSON com o erro
                                    return jsonify({'error': f'{e}'}), 500

                            elif status == 500:
                                return jsonify({'Erro': f'Sem resposta do Banco[{from_bank_id}] do destinatário'}), 400

                            else:
                                # Se não conseguir fazer a transferência, o valor é estornado
                                self.accounts[str(from_account_id)]['saldo'] += amount
                                return jsonify({'error': 'transferência não concluída, problema no outro banco'}), 400
                        else:
                            # Retorna um JSON com o ID da transação e o status
                            return jsonify({'error': 'Saldo insuficiente. Operação cancelada'}), 400

                elif verificacao == 500:
                    return jsonify({'Erro': f'Banco não encontrado: {to_bank_id}'}), 400

                else:
                    # Teste
                    return jsonify({'Erro': f'Problemas na verificação das contas. Uma das contas não existe'}), 400

            # Se a transferência for entre dois bancos que não estejam gerenciando a transferência
            elif from_bank_id is not self.bank_id:

                # Para verificar se o usuário do banco remetente existe
                body_check_from_user = {
                    'to_bank_id': from_bank_id,
                    'to_account_id': from_account_id,
                }
                # Para verificar se o usuário do banco destinatário existe
                body_check_to_user = {
                    'to_bank_id': to_bank_id,
                    'to_account_id': to_account_id,
                }

                verificacao_remetente = self.verifica_existencia_conta(body_check_from_user, from_bank_id)

                if verificacao_remetente == 200:

                    verificacao_destinatario = self.verifica_existencia_conta(body_check_to_user, to_bank_id)

                    if verificacao_destinatario == 200:

                        # Tenta realizar a transferencia
                        status = self.envia_transferencia_outro_para_outro(from_bank_id=from_bank_id,
                                                                           transaction=request.json)
                        if status == 200:
                            try:
                                # Retorna um JSON com o ID da transação e o status
                                return jsonify({
                                    'Solicitação enviada': f'Transferência do Banco[{from_bank_id}] para o Banco[{to_bank_id}]'}), 200
                            except Exception as e:
                                # Retorna um JSON com o ID da transação e o status
                                return jsonify({f'{e}': "Transação não gerada"}), 500

                        # Sem resposta do banco remetente
                        elif status == 500:
                            return jsonify({'Erro': f'Sem resposta do Banco[{to_bank_id}] remetente'}), 400

                    elif verificacao_destinatario == 500:
                        return jsonify({'Erro': f'Sem resposta do Banco[{to_bank_id}] do destinatário'}), 400
                    else:
                        return jsonify({
                            'Erro': f'A conta do destinatário de id[{to_account_id}] não existe no Banco[{to_bank_id}]'}), 400

                elif verificacao_remetente == 500:
                    # Teste
                    return jsonify({'Erro': f'Sem resposta do Banco[{from_bank_id}] do remetente'}), 400
                else:
                    return jsonify({
                        'Erro': f'A conta do remetente de id[{from_account_id}] não existe no Banco[{from_bank_id}]'}), 400

            else:
                return jsonify({'Erro': 'Nenhuma das condições atendida'})

        @self.app.route('/banco/conta/<account_id>/transacao/<transaction_id>', methods=['GET'])
        def get_transaction(account_id, transaction_id):
            # Verifica se a transação existe
            if transaction_id in self.accounts[str(account_id)]["transacoes"]:
                # Retorna um JSON com as informações da transação
                return jsonify(self.accounts[account_id]["transacoes"][transaction_id]), 200
            else:
                # Retorna um erro 404 (Not Found) se a transação não existir
                return jsonify({'error': 'Transaction not found'}), 404

        @self.app.route('/banco/conta/<account_id>/transacao', methods=['GET'])
        def get_all_transactions(account_id):
            # Verifica se a conta existe
            if str(account_id) in self.accounts:
                if len(self.accounts[account_id]["transacoes"]) > 0:
                    transacoes = {}

                    for key, value in self.accounts[account_id]["transacoes"].items():
                        transacoes[key] = {
                            'ID da transação': value['id'],
                            'Data': value["date_time"],
                            'Banco de origem': value["from_bank_id"],
                            'ID da conta de origem': value["from_account_id"],
                            'Banco de destino': value["to_bank_id"],
                            'ID da conta de destino': value["to_account_id"],
                            'Valor da transação': value["amount"],
                            'Status da transação': value["status"]
                        }
                        return jsonify(transacoes), 200
                else:
                    return jsonify({"Erro": "Sem transações nessa conta"}), 400
            else:
                return jsonify({"Erro": "Usuario nao encontrado"}), 404
        """
        @self.app.route('/transaction/<transaction_id>', methods=['DELETE'])
        def cancel_transaction(transaction_id):
            # Verifica se a transação existe e está pendente
            if transaction_id in self.transactions and self.transactions[transaction_id]['status'] == 'pending':
                # Cancela a transação e reverte a transferência entre as contas
                from_bank_id = self.transactions[transaction_id]['from_bank_id']
                from_account_id = self.transactions[transaction_id]['from_account_id']
                to_bank_id = self.transactions[transaction_id]['to_bank_id']
                to_account_id = self.transactions[transaction_id]['to_account_id']
                amount = self.transactions[transaction_id]['amount']
                self.accounts[from_bank_id][from_account_id]['balance'] += amount
                self.accounts[to_bank_id][to_account_id]['balance'] -= amount
                self.transactions[transaction_id]['status'] = 'cancelled'

                # Retorna um JSON com o ID da transação e o status
                return jsonify({'id': transaction_id, 'status': self.transactions[transaction_id]['status']}), 200
            else:
                # Retorna um erro 400 (Bad Request) se a transação não puder ser cancelada
                return jsonify({'error': 'Transaction cannot be cancelled'}), 400
        """

        @self.app.route('/banco/transferencia/existencia_conta', methods=['POST'])
        def escuta_existencia_conta():
            to_account_id = request.json.get('to_account_id')

            if str(to_account_id) in self.accounts:
                return 'A conta existe', 200
            return 'A conta não existe', 404

        @self.app.route('/banco/transferencia/esse_para_outro', methods=['POST'])
        def esse_para_outro():
            # Extrai dados do corpo da requisição
            transacao = request.json

            transaction_id = request.json.get('id')
            to_account_id = request.json.get('to_account_id')
            amount = request.json.get('amount')

            # Ativa o semáforo da conta correspondente
            with self.clients_semaphore[str(to_account_id)]:
                try:
                    # Atualiza a quantia na conta
                    self.accounts[str(to_account_id)]['saldo'] += amount
                    # Cria a transação
                    self.accounts[str(to_account_id)]["transacoes"][transaction_id] = transacao
                    # Atualiza o status da transação para "concluída"
                    self.accounts[str(to_account_id)]["transacoes"][transaction_id]['status'] = 'completed'

                    # Retorna um JSON com o ID da transação e o status
                    return jsonify({'id': transaction_id,
                                    'status': self.accounts[str(to_account_id)]["transacoes"][transaction_id][
                                        'status']}), 200
                except Exception as e:
                    return jsonify({f'{e}': 'Transaction not completed'}), 404

        @self.app.route('/banco/transferencia/outro_para_outro', methods=['POST'])
        def outro_para_outro():
            transaction = request.json
            from_bank_id = request.json.get('from_bank_id')
            """
            O próprio banco vai fazer o papel de cliente e solicitar para ele mesmo que a transferencia seja feita
            """
            request_var = requests.post(f'http://localhost:800{from_bank_id}/banco/transferencia', json=transaction)
            if request_var.status_code == 200:
                return jsonify({'OK': "Transferência feita com sucesso"}), 200
            return jsonify({'erro': "Transferência cancelada"}), 400

    def verifica_existencia_conta(self, body_check_user, to_bank_id):
        try:
            to_bank_id = str(to_bank_id)
            check_user = requests.post(f'http://localhost:800{to_bank_id}/banco/transferencia/existencia_conta',
                                       json=body_check_user)

            if check_user.status_code == 200:
                return 200
            return 404
        except Exception as e:
            return f'{e}', 500

    """
    Essa função tem como objetivo enviar a transferencia
    do banco atual para outro banco
    """

    def envia_transferencia_esse_para_outro(self, transaction, to_bank_id):
        try:
            to_bank_id = str(to_bank_id)
            request_var = requests.post(f'http://localhost:800{to_bank_id}/banco/transferencia/esse_para_outro',
                                        json=transaction)

            if request_var.status_code == 200:
                return 200
            return 404
        except Exception as e:
            return f'{e}', 500

    """
    Essa função tem como objetivo pedir para outro banco fazer a transferência para
    um terceiro banco
    """

    def envia_transferencia_outro_para_outro(self, from_bank_id, transaction):
        try:
            from_bank_id = str(from_bank_id)
            request_var = requests.post(f'http://localhost:800{from_bank_id}/banco/transferencia/outro_para_outro',
                                        json=transaction)

            if request_var.status_code == 200:
                return 200
            return request_var.status_code
        except Exception as e:
            return f'{e}', 500

    def flask_run(self):
        self.app.run(port=self.port_flask, debug=True)


if __name__ == '__main__':
    bank = Bank(1, "localhost", 8001, accounts=contas)
    bank.flask_run()
