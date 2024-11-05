from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
import requests
from datetime import datetime
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Configuração do Banco de Dados
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Credenciais de login
USUARIO = os.getenv('USUARIO')
SENHA = os.getenv('SENHA')

# Definição dos meses para o dropdown
MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Função para formatar valores em reais manualmente
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Modelo de dados para investimentos no banco de dados
class Investimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ano = db.Column(db.String(4), nullable=False)
    mes = db.Column(db.String(3), nullable=False)
    investimento = db.Column(db.Float, nullable=False)
    quantidade_btc = db.Column(db.Float, nullable=False)

# Criar as tabelas no banco de dados (execute uma vez)
with app.app_context():
    db.create_all()

# Função para obter a cotação atual do BTC em reais
def obter_cotacao_btc():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl"
        response = requests.get(url).json()
        return response['bitcoin']['brl']
    except:
        return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USUARIO and password == SENHA:
            session['logged_in'] = True
            flash("Login bem-sucedido! Redirecionando...")
            return redirect(url_for('loading'))
        else:
            flash('Credenciais inválidas. Tente novamente.')
    return render_template('login.html')

@app.route('/loading')
def loading():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("loading.html")

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("index.html")

@app.route('/selecionar_ano', methods=['GET', 'POST'])
def selecionar_ano():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        ano = request.form['ano']
        return redirect(url_for('resumo', ano=ano))
    anos = [str(datetime.now().year - i) for i in range(5)]
    return render_template("selecionar_ano.html", anos=anos)

@app.route('/resumo/<ano>')
def resumo(ano):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # Obter dados do banco de dados para o ano selecionado
    resumo_mensal = []
    for mes in MESES:
        investimentos = Investimento.query.filter_by(ano=ano, mes=mes).all()
        investimento_total = sum([inv.investimento for inv in investimentos])
        quantidade_btc_total = sum([inv.quantidade_btc for inv in investimentos])
        investimento_formatado = formatar_moeda(investimento_total)
        resumo_mensal.append({"mes": mes, "investimento": investimento_formatado, "quantidade_btc": quantidade_btc_total})

    return render_template("resumo.html", resumo_mensal=resumo_mensal, ano=ano)

@app.route('/lucro')
def lucro():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    anos = [str(datetime.now().year - i) for i in range(5)]
    total_investido = 0
    total_btc = 0

    for ano in anos:
        investimentos = Investimento.query.filter_by(ano=ano).all()
        total_investido += sum([inv.investimento for inv in investimentos])
        total_btc += sum([inv.quantidade_btc for inv in investimentos])

    cotacao_btc = obter_cotacao_btc()
    if cotacao_btc is None:
        flash("Erro ao obter a cotação do BTC.")
        lucro_prejuizo = None
    else:
        valor_total_em_reais = total_btc * cotacao_btc
        lucro_prejuizo = valor_total_em_reais - total_investido

        total_investido = formatar_moeda(total_investido)
        valor_total_em_reais = formatar_moeda(valor_total_em_reais)
        lucro_prejuizo_formatado = formatar_moeda(lucro_prejuizo)
        cotacao_btc = formatar_moeda(cotacao_btc)

    return render_template(
        "lucro.html",
        total_investido=total_investido,
        total_btc=total_btc,
        valor_total_em_reais=valor_total_em_reais,
        lucro_prejuizo_formatado=lucro_prejuizo_formatado,
        cotacao_btc=cotacao_btc,
        lucro_prejuizo=lucro_prejuizo
    )

@app.route('/editar', methods=['GET', 'POST'])
def editar():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    ano = request.args.get('ano')
    if request.method == 'POST':
        mes_selecionado = request.form.get('mes')
        investimentos = Investimento.query.filter_by(ano=ano, mes=mes_selecionado).all()
        valores_atuais = [{"investimento": inv.investimento, "quantidade_btc": inv.quantidade_btc} for inv in investimentos]
        return render_template("editar_mes.html", mes_selecionado=mes_selecionado, valores_atuais=valores_atuais, ano=ano)

    return render_template("selecionar_mes.html", meses=MESES, ano=ano)

@app.route('/salvar_edicao', methods=['POST'])
def salvar_edicao():
    ano = request.form.get('ano')
    mes_selecionado = request.form.get('mes')
    novos_investimentos = request.form.getlist('investimento[]')
    novas_quantidades_btc = request.form.getlist('quantidade_btc[]')

    # Apagar investimentos existentes para o mês selecionado
    Investimento.query.filter_by(ano=ano, mes=mes_selecionado).delete()

    # Adicionar novos valores
    for investimento, quantidade_btc in zip(novos_investimentos, novas_quantidades_btc):
        if investimento and quantidade_btc:
            novo_investimento = Investimento(
                ano=ano,
                mes=mes_selecionado,
                investimento=float(investimento.replace(',', '.')),
                quantidade_btc=float(quantidade_btc.replace(',', '.'))
            )
            db.session.add(novo_investimento)

    db.session.commit()
    flash("Alterações salvas com sucesso!")
    return redirect(url_for('resumo', ano=ano))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    get_flashed_messages()
    flash("Você foi desconectado.")
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
