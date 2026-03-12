from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import uuid

# Twilio (opcional — só importa se instalado)
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_OK = True
except ImportError:
    TWILIO_OK = False

app = Flask(__name__)
app.secret_key = 'encaixamento_secret_2024'

DATA_FILE = 'data/agendamentos.json'
CONFIG_FILE = 'data/config.json'

# ─────────────────────────────────────────────
#  Configurações (edite aqui ou via painel admin)
# ─────────────────────────────────────────────
DEFAULT_CONFIG = {
    "clinica_nome": "Encaixamente",
    "psianalista_nome": "Dra. Ana Silva",
    "email_remetente": "",          # Ex: clinica@gmail.com
    "email_senha": "",              # Senha de app Gmail
    "email_destinatario": "",       # Email da psicanalista
    "telegram_bot_token": "",       # Token do bot Telegram
    "telegram_chat_id": "",         # Chat ID da psicanalista
    "twilio_account_sid": "",       # Account SID da Twilio
    "twilio_auth_token": "",        # Auth Token da Twilio
    "twilio_whatsapp_from": "whatsapp:+14155238886",  # Número Twilio (sandbox padrão)
    "twilio_whatsapp_to": "",       # WhatsApp da psicanalista ex: whatsapp:+5585999999999
    "horarios_disponiveis": {
        "segunda": ["09:00","10:00","11:00","14:00","15:00","16:00","17:00"],
        "terca":   ["09:00","10:00","11:00","14:00","15:00","16:00","17:00"],
        "quarta":  ["09:00","10:00","11:00","14:00","15:00","16:00","17:00"],
        "quinta":  ["09:00","10:00","11:00","14:00","15:00","16:00","17:00"],
        "sexta":   ["09:00","10:00","11:00","14:00","15:00"]
    },
    "duracao_consulta_min": 50,
    "valor_consulta": "R$ 150,00"
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        os.makedirs('data', exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    with open(CONFIG_FILE, 'r') as f:
        cfg = json.load(f)
    # Migrar chave antiga com acento se existir
    if 'psicanálista_nome' in cfg:
        cfg['psianalista_nome'] = cfg.pop('psicanálista_nome')
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    # Garantir que a chave sempre existe
    if 'psianalista_nome' not in cfg:
        cfg['psianalista_nome'] = 'Dra. Ana Silva'
    return cfg

def load_agendamentos():
    if not os.path.exists(DATA_FILE):
        os.makedirs('data', exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            json.dump([], f)
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_agendamentos(agendamentos):
    with open(DATA_FILE, 'w') as f:
        json.dump(agendamentos, f, ensure_ascii=False, indent=2)

def get_dia_semana(data_str):
    data = datetime.strptime(data_str, '%Y-%m-%d')
    dias = ['segunda','terca','quarta','quinta','sexta','sabado','domingo']
    return dias[data.weekday()]

def horarios_disponiveis(data_str):
    config = load_config()
    dia = get_dia_semana(data_str)
    todos = config['horarios_disponiveis'].get(dia, [])
    agendamentos = load_agendamentos()
    ocupados = [a['horario'] for a in agendamentos 
                if a['data'] == data_str and a['status'] != 'cancelado']
    return [h for h in todos if h not in ocupados]

def enviar_email(agendamento):
    config = load_config()
    if not config.get('email_remetente') or not config.get('email_destinatario'):
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🗓️ Novo Agendamento — {agendamento['nome']}"
        msg['From'] = config['email_remetente']
        msg['To'] = config['email_destinatario']
        
        html = f"""
        <div style="font-family:Georgia,serif;max-width:520px;margin:auto;background:#faf8f5;padding:32px;border-radius:12px;">
          <h2 style="color:#6b4c3b;margin-bottom:4px;">Encaixamente</h2>
          <p style="color:#a08070;font-size:13px;margin-top:0;">Clínica de Psicanálise</p>
          <hr style="border:none;border-top:1px solid #e8dfd6;margin:20px 0;">
          <h3 style="color:#3d2b1f;">Novo agendamento recebido</h3>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:8px 0;color:#a08070;font-size:13px;">Cliente</td>
                <td style="padding:8px 0;color:#3d2b1f;font-weight:bold;">{agendamento['nome']}</td></tr>
            <tr><td style="padding:8px 0;color:#a08070;font-size:13px;">Data</td>
                <td style="padding:8px 0;color:#3d2b1f;">{agendamento['data_formatada']}</td></tr>
            <tr><td style="padding:8px 0;color:#a08070;font-size:13px;">Horário</td>
                <td style="padding:8px 0;color:#3d2b1f;">{agendamento['horario']}</td></tr>
            <tr><td style="padding:8px 0;color:#a08070;font-size:13px;">Telefone</td>
                <td style="padding:8px 0;color:#3d2b1f;">{agendamento['telefone']}</td></tr>
            <tr><td style="padding:8px 0;color:#a08070;font-size:13px;">Email</td>
                <td style="padding:8px 0;color:#3d2b1f;">{agendamento['email']}</td></tr>
            <tr><td style="padding:8px 0;color:#a08070;font-size:13px;">Motivo</td>
                <td style="padding:8px 0;color:#3d2b1f;">{agendamento.get('motivo','—')}</td></tr>
          </table>
          <hr style="border:none;border-top:1px solid #e8dfd6;margin:20px 0;">
          <p style="color:#a08070;font-size:12px;">ID do agendamento: {agendamento['id']}</p>
        </div>"""
        
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(config['email_remetente'], config['email_senha'])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Erro email: {e}")
        return False

def enviar_whatsapp(agendamento):
    """Envia notificação WhatsApp via Twilio para a psicanalista."""
    config = load_config()
    sid  = config.get('twilio_account_sid','').strip()
    tok  = config.get('twilio_auth_token','').strip()
    frm  = config.get('twilio_whatsapp_from','').strip()
    to   = config.get('twilio_whatsapp_to','').strip()
    if not (sid and tok and frm and to):
        return False
    if not TWILIO_OK:
        print("Twilio não instalado. Rode: pip install twilio")
        return False
    try:
        client = TwilioClient(sid, tok)
        corpo = (
            f"🌿 *Novo Agendamento — Encaixamente*\n\n"
            f"👤 Cliente: {agendamento['nome']}\n"
            f"📅 Data: {agendamento['data_formatada']}\n"
            f"⏰ Horário: {agendamento['horario']}\n"
            f"📞 Telefone: {agendamento['telefone']}\n"
            f"✉️ Email: {agendamento['email']}\n"
            f"💬 Motivo: {agendamento.get('motivo') or '—'}\n\n"
            f"ID: {agendamento['id']}"
        )
        client.messages.create(body=corpo, from_=frm, to=to)
        return True
    except Exception as e:
        print(f"Erro WhatsApp Twilio: {e}")
        return False

def enviar_telegram(agendamento):
    config = load_config()
    if not config.get('telegram_bot_token') or not config.get('telegram_chat_id'):
        return False
    try:
        token = config['telegram_bot_token']
        chat_id = config['telegram_chat_id']
        texto = (
            f"🌿 *Novo Agendamento — Encaixamente*\n\n"
            f"👤 *Cliente:* {agendamento['nome']}\n"
            f"📅 *Data:* {agendamento['data_formatada']}\n"
            f"⏰ *Horário:* {agendamento['horario']}\n"
            f"📞 *Telefone:* {agendamento['telefone']}\n"
            f"✉️ *Email:* {agendamento['email']}\n"
            f"💬 *Motivo:* {agendamento.get('motivo','—')}\n\n"
            f"_ID: {agendamento['id']}_"
        )
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={'chat_id': chat_id, 'text': texto, 'parse_mode': 'Markdown'}, timeout=5)
        return True
    except Exception as e:
        print(f"Erro Telegram: {e}")
        return False

# ─────────────────────────────────────────────
#  Rotas
# ─────────────────────────────────────────────

@app.route('/')
def index():
    config = load_config()
    return render_template('index.html', config=config, psianalista=config.get('psianalista_nome','Dra. Ana Silva'))

@app.route('/agendar')
def agendar():
    config = load_config()
    return render_template('agendar.html', config=config, psianalista=config.get('psianalista_nome','Dra. Ana Silva'))

@app.route('/admin')
def admin():
    config = load_config()
    agendamentos = load_agendamentos()
    hoje = datetime.now().date()
    futuros = [a for a in agendamentos 
               if datetime.strptime(a['data'],'%Y-%m-%d').date() >= hoje 
               and a['status'] != 'cancelado']
    futuros.sort(key=lambda x: (x['data'], x['horario']))
    return render_template('admin.html', config=config, agendamentos=futuros, total=len(agendamentos), psianalista=config.get('psianalista_nome','Dra. Ana Silva'))

@app.route('/api/horarios')
def api_horarios():
    data = request.args.get('data')
    if not data:
        return jsonify({'error': 'Data não informada'}), 400
    try:
        d = datetime.strptime(data, '%Y-%m-%d').date()
        if d < datetime.now().date():
            return jsonify({'horarios': [], 'msg': 'Data no passado'})
        dia = get_dia_semana(data)
        config = load_config()
        if dia not in config['horarios_disponiveis']:
            return jsonify({'horarios': [], 'msg': 'Sem atendimento neste dia'})
        return jsonify({'horarios': horarios_disponiveis(data)})
    except:
        return jsonify({'error': 'Data inválida'}), 400

@app.route('/api/agendar', methods=['POST'])
def api_agendar():
    dados = request.get_json()
    required = ['nome','email','telefone','data','horario']
    for campo in required:
        if not dados.get(campo):
            return jsonify({'ok': False, 'msg': f'Campo obrigatório: {campo}'}), 400

    # Checar disponibilidade
    disponiveis = horarios_disponiveis(dados['data'])
    if dados['horario'] not in disponiveis:
        return jsonify({'ok': False, 'msg': 'Horário não disponível'}), 409

    data_obj = datetime.strptime(dados['data'], '%Y-%m-%d')
    dias_ptbr = ['Segunda-feira','Terça-feira','Quarta-feira',
                 'Quinta-feira','Sexta-feira','Sábado','Domingo']
    meses = ['','janeiro','fevereiro','março','abril','maio','junho',
             'julho','agosto','setembro','outubro','novembro','dezembro']
    data_fmt = f"{dias_ptbr[data_obj.weekday()]}, {data_obj.day} de {meses[data_obj.month]} de {data_obj.year}"

    agendamento = {
        'id': str(uuid.uuid4())[:8].upper(),
        'nome': dados['nome'],
        'email': dados['email'],
        'telefone': dados['telefone'],
        'data': dados['data'],
        'data_formatada': data_fmt,
        'horario': dados['horario'],
        'motivo': dados.get('motivo',''),
        'status': 'confirmado',
        'criado_em': datetime.now().isoformat()
    }

    agendamentos = load_agendamentos()
    agendamentos.append(agendamento)
    save_agendamentos(agendamentos)

    # Notificações (não bloqueia se falhar)
    enviar_email(agendamento)
    enviar_telegram(agendamento)
    enviar_whatsapp(agendamento)

    return jsonify({'ok': True, 'id': agendamento['id'], 'data_formatada': data_fmt})

@app.route('/api/cancelar', methods=['POST'])
def api_cancelar():
    dados = request.get_json()
    ag_id = dados.get('id','').upper()
    email = dados.get('email','').lower()
    agendamentos = load_agendamentos()
    for a in agendamentos:
        if a['id'] == ag_id and a['email'].lower() == email:
            if a['status'] == 'cancelado':
                return jsonify({'ok': False, 'msg': 'Já cancelado'})
            a['status'] = 'cancelado'
            save_agendamentos(agendamentos)
            return jsonify({'ok': True})
    return jsonify({'ok': False, 'msg': 'Agendamento não encontrado'}), 404

@app.route('/api/config', methods=['GET','POST'])
def api_config():
    if request.method == 'GET':
        c = load_config()
        # Não retornar senhas
        c.pop('email_senha', None)
        return jsonify(c)
    dados = request.get_json()
    config = load_config()
    for k, v in dados.items():
        config[k] = v
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True})

@app.route('/api/historico')
def api_historico():
    """Retorna histórico de agendamentos de um cliente pelo email."""
    email = request.args.get('email','').lower().strip()
    if not email:
        return jsonify({'agendamentos': []})
    agendamentos = load_agendamentos()
    historico = [a for a in agendamentos if a['email'].lower() == email]
    historico.sort(key=lambda x: (x['data'], x['horario']), reverse=True)
    return jsonify({'agendamentos': historico})

# ─────────────────────────────────────────────
#  Bot de conversa — Sistema completo com histórico
# ─────────────────────────────────────────────
BOT_ESTADOS = {}

def fmt_data_curta(data_str):
    try:
        d = datetime.strptime(data_str, '%Y-%m-%d')
        dias = ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom']
        meses = ['','jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
        return f"{dias[d.weekday()]}, {d.day}/{meses[d.month]}/{d.year}"
    except:
        return data_str

def fmt_data_longa(data_str):
    try:
        d = datetime.strptime(data_str, '%Y-%m-%d')
        dias = ['Segunda-feira','Terça-feira','Quarta-feira','Quinta-feira','Sexta-feira','Sábado','Domingo']
        meses = ['','janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro']
        return f"{dias[d.weekday()]}, {d.day} de {meses[d.month]} de {d.year}"
    except:
        return data_str

def _salvar_estado(session_id, estado):
    BOT_ESTADOS[session_id] = estado

def menu_principal(config):
    return {
        'resposta': f"Como posso ajudar? 🌿",
        'opcoes': ['📅 Agendar consulta','📋 Meu histórico','🔍 Verificar agendamento',
                   '🔄 Reagendar consulta','❌ Cancelar consulta','ℹ️ Sobre a clínica']
    }

@app.route('/api/bot', methods=['POST'])
def api_bot():
    dados = request.get_json()
    session_id = dados.get('session_id', 'default')
    msg_raw = dados.get('mensagem', '').strip()
    msg = msg_raw.lower()

    estado = BOT_ESTADOS.get(session_id, {'etapa': 'inicio', 'dados': {}})
    config = load_config()

    def salvar(etapa=None):
        if etapa:
            estado['etapa'] = etapa
        _salvar_estado(session_id, estado)

    def reset_menu():
        estado['etapa'] = 'menu'
        estado['dados'] = {}
        _salvar_estado(session_id, estado)
        return jsonify(menu_principal(config))

    # ── Atalhos globais ──
    if estado['etapa'] == 'inicio' or msg in ['oi','olá','ola','menu','início','inicio','recomeçar','voltar']:
        estado['etapa'] = 'menu'
        estado['dados'] = {}
        _salvar_estado(session_id, estado)
        return jsonify({
            'resposta': f"Olá! 🌿 Bem-vindo(a) à *{config['clinica_nome']}*.\nSou o assistente virtual. Como posso ajudar?",
            'opcoes': ['📅 Agendar consulta','📋 Meu histórico','🔍 Verificar agendamento',
                       '🔄 Reagendar consulta','❌ Cancelar consulta','ℹ️ Sobre a clínica']
        })

    if '↩️' in msg or msg == 'menu principal':
        return reset_menu()

    # ── SOBRE ──
    if 'sobre' in msg or 'ℹ️' in msg or 'informaç' in msg:
        return jsonify({
            'resposta': f"🌿 *{config['clinica_nome']}* — Clínica de Psicanálise\n\n"
                        f"💼 Psicanalista: {config['psianalista_nome']}\n"
                        f"💰 Valor da sessão: {config['valor_consulta']}\n"
                        f"⏱️ Duração: {config['duracao_consulta_min']} minutos\n"
                        f"📆 Atendimento: segunda a sexta",
            'opcoes': ['📅 Agendar consulta','↩️ Menu principal']
        })

    # ── HISTÓRICO ──
    if 'histórico' in msg or 'meu hist' in msg or '📋' in msg:
        estado['etapa'] = 'historico_email'
        salvar()
        return jsonify({'resposta': 'Para ver seu histórico, informe seu *e-mail* cadastrado:', 'opcoes': []})

    if estado['etapa'] == 'historico_email':
        email = msg_raw.strip()
        agendamentos = load_agendamentos()
        hist = [a for a in agendamentos if a['email'].lower() == email.lower()]
        hist.sort(key=lambda x: (x['data'], x['horario']), reverse=True)
        if not hist:
            return reset_menu() if True else None  # fallback
        hoje = datetime.now().date()
        futuros = [a for a in hist if datetime.strptime(a['data'],'%Y-%m-%d').date() >= hoje and a['status']=='confirmado']
        passados = [a for a in hist if datetime.strptime(a['data'],'%Y-%m-%d').date() < hoje or a['status']=='cancelado']
        linhas = []
        if futuros:
            linhas.append("📅 *Próximas consultas:*")
            for a in futuros[:3]:
                linhas.append(f"  • {fmt_data_curta(a['data'])} às {a['horario']} — ID: *{a['id']}*")
        if passados:
            linhas.append("\n🗂️ *Histórico anterior:*")
            for a in passados[:4]:
                st = '✅' if a['status']=='confirmado' else '❌'
                linhas.append(f"  {st} {fmt_data_curta(a['data'])} às {a['horario']} — ID: {a['id']}")
        if not hist:
            linhas = ["Nenhum agendamento encontrado para este e-mail."]
        estado['etapa'] = 'menu'
        estado['dados'] = {}
        salvar()
        return jsonify({
            'resposta': '\n'.join(linhas) or 'Nenhum agendamento encontrado.',
            'opcoes': ['📅 Novo agendamento','🔄 Reagendar consulta','↩️ Menu principal']
        })

    # ── VERIFICAR ──
    if 'verificar' in msg or '🔍' in msg:
        estado['etapa'] = 'verificar_id'
        salvar()
        return jsonify({'resposta': 'Informe o *ID do agendamento* (ex: A1B2C3D4):', 'opcoes': []})

    if estado['etapa'] == 'verificar_id':
        ag_id = msg_raw.strip().upper()
        agendamentos = load_agendamentos()
        encontrado = next((a for a in agendamentos if a['id'] == ag_id), None)
        estado['etapa'] = 'menu'
        salvar()
        if encontrado:
            st = '✅ Confirmado' if encontrado['status']=='confirmado' else '❌ Cancelado'
            return jsonify({
                'resposta': f"*Agendamento {ag_id}*\n\n"
                           f"👤 {encontrado['nome']}\n"
                           f"📅 {encontrado['data_formatada']}\n"
                           f"⏰ {encontrado['horario']}\n"
                           f"Status: {st}",
                'opcoes': ['🔄 Reagendar consulta','❌ Cancelar consulta','↩️ Menu principal']
            })
        return jsonify({'resposta': 'Agendamento não encontrado. Verifique o ID.', 'opcoes': ['↩️ Menu principal']})

    # ── CANCELAR ──
    if ('cancelar' in msg or '❌' in msg) and estado['etapa'] == 'menu':
        estado['etapa'] = 'cancelar_id'
        salvar()
        return jsonify({'resposta': 'Informe o *ID do agendamento* a cancelar:', 'opcoes': []})

    if estado['etapa'] == 'cancelar_id':
        estado['dados']['cancel_id'] = msg_raw.strip().upper()
        estado['etapa'] = 'cancelar_email'
        salvar()
        return jsonify({'resposta': 'Confirme seu *e-mail* para continuar:', 'opcoes': []})

    if estado['etapa'] == 'cancelar_email':
        ag_id = estado['dados'].get('cancel_id','')
        agendamentos = load_agendamentos()
        for a in agendamentos:
            if a['id'] == ag_id and a['email'].lower() == msg_raw.strip().lower():
                if a['status'] == 'cancelado':
                    estado['etapa'] = 'menu'; salvar()
                    return jsonify({'resposta': 'Este agendamento já foi cancelado.', 'opcoes': ['↩️ Menu principal']})
                a['status'] = 'cancelado'
                save_agendamentos(agendamentos)
                estado['etapa'] = 'menu'; estado['dados'] = {}; salvar()
                return jsonify({'resposta': f"✅ Agendamento *{ag_id}* cancelado com sucesso.", 'opcoes': ['📅 Novo agendamento','↩️ Menu principal']})
        estado['etapa'] = 'menu'; salvar()
        return jsonify({'resposta': 'ID ou e-mail incorretos. Tente novamente.', 'opcoes': ['↩️ Menu principal']})

    # ── REAGENDAR ──
    if 'reagendar' in msg or '🔄' in msg:
        estado['etapa'] = 'reagendar_id'
        salvar()
        return jsonify({'resposta': 'Informe o *ID do agendamento* que deseja reagendar:', 'opcoes': []})

    if estado['etapa'] == 'reagendar_id':
        ag_id = msg_raw.strip().upper()
        agendamentos = load_agendamentos()
        encontrado = next((a for a in agendamentos if a['id'] == ag_id and a['status']=='confirmado'), None)
        if not encontrado:
            estado['etapa'] = 'menu'; salvar()
            return jsonify({'resposta': 'Agendamento não encontrado ou já cancelado.', 'opcoes': ['↩️ Menu principal']})
        estado['dados']['reagendar_id'] = ag_id
        estado['dados']['reagendar_email_check'] = True
        # pré-preenche nome/email/telefone do ag anterior
        estado['dados']['nome'] = encontrado['nome']
        estado['dados']['email'] = encontrado['email']
        estado['dados']['telefone'] = encontrado['telefone']
        estado['dados']['motivo'] = encontrado.get('motivo','')
        estado['etapa'] = 'reagendar_confirma_email'
        salvar()
        return jsonify({'resposta': f"Agendamento encontrado: *{fmt_data_curta(encontrado['data'])}* às *{encontrado['horario']}*.\n\nConfirme seu *e-mail* para reagendar:", 'opcoes': []})

    if estado['etapa'] == 'reagendar_confirma_email':
        if msg_raw.strip().lower() != estado['dados']['email'].lower():
            estado['etapa'] = 'menu'; salvar()
            return jsonify({'resposta': 'E-mail não confere. Operação cancelada.', 'opcoes': ['↩️ Menu principal']})
        estado['etapa'] = 'data'
        salvar()
        return jsonify({'resposta': 'E-mail confirmado! ✅\n\nEscolha a *nova data* para a consulta:', 'opcoes': [], 'acao': 'mostrar_data'})

    # ── AGENDAR ──
    if 'agendar' in msg or '📅' in msg:
        estado['etapa'] = 'nome'
        estado['dados'] = {}
        salvar()
        return jsonify({'resposta': 'Ótimo! Vamos agendar sua consulta. 😊\n\nQual é o seu *nome completo*?', 'opcoes': []})

    if estado['etapa'] == 'nome':
        nome = msg_raw.strip()
        if len(nome) < 3:
            return jsonify({'resposta': 'Por favor, informe seu nome completo.', 'opcoes': []})
        estado['dados']['nome'] = nome
        estado['etapa'] = 'email'; salvar()
        return jsonify({'resposta': f"Prazer, *{nome.split()[0]}*! 😊\n\nQual é o seu *e-mail*?", 'opcoes': []})

    if estado['etapa'] == 'email':
        email = msg_raw.strip()
        if '@' not in email:
            return jsonify({'resposta': 'E-mail inválido. Tente novamente.', 'opcoes': []})
        estado['dados']['email'] = email
        # Verificar se tem histórico
        agendamentos = load_agendamentos()
        hist = [a for a in agendamentos if a['email'].lower() == email.lower()]
        estado['etapa'] = 'telefone'; salvar()
        extra = ''
        if hist:
            confirmados = [a for a in hist if a['status']=='confirmado']
            extra = f"\n\n_(Encontrei {len(hist)} agendamento(s) anteriores em sua conta.)_"
        return jsonify({'resposta': f"Obrigada! 😊{extra}\n\nQual é o seu *telefone* (com DDD)?", 'opcoes': []})

    if estado['etapa'] == 'telefone':
        estado['dados']['telefone'] = msg_raw.strip()
        estado['etapa'] = 'data'; salvar()
        return jsonify({'resposta': 'Escolha a *data* desejada para a consulta:', 'opcoes': [], 'acao': 'mostrar_data'})

    if estado['etapa'] == 'data':
        estado['dados']['data'] = msg_raw.strip()
        estado['etapa'] = 'horario'; salvar()
        return jsonify({'resposta': 'Ótimo! Escolha o *horário* disponível:', 'opcoes': [], 'acao': 'mostrar_horarios', 'data': estado['dados']['data']})

    if estado['etapa'] == 'horario':
        estado['dados']['horario'] = msg_raw.strip()
        estado['etapa'] = 'motivo'; salvar()
        return jsonify({'resposta': 'Gostaria de compartilhar o *motivo* da consulta? (opcional)', 'opcoes': ['Pular']})

    if estado['etapa'] == 'motivo':
        motivo = msg_raw.strip()
        if motivo.lower() == 'pular':
            motivo = estado['dados'].get('motivo','')
        estado['dados']['motivo'] = motivo
        estado['etapa'] = 'confirmar'
        d = estado['dados']
        salvar()
        return jsonify({
            'resposta': f"📋 *Resumo do agendamento:*\n\n"
                       f"👤 Nome: {d['nome']}\n"
                       f"✉️ Email: {d['email']}\n"
                       f"📞 Telefone: {d['telefone']}\n"
                       f"📅 Data: {fmt_data_curta(d['data'])}\n"
                       f"⏰ Horário: {d['horario']}\n\n"
                       f"Confirmar agendamento?",
            'opcoes': ['✅ Confirmar','❌ Cancelar']
        })

    if estado['etapa'] == 'confirmar':
        if 'confirmar' in msg or '✅' in msg:
            d = estado['dados']
            # Se reagendamento, cancelar o anterior
            if d.get('reagendar_id'):
                agendamentos = load_agendamentos()
                for a in agendamentos:
                    if a['id'] == d['reagendar_id']:
                        a['status'] = 'cancelado'
                save_agendamentos(agendamentos)

            # Criar novo agendamento diretamente
            data_obj = datetime.strptime(d['data'], '%Y-%m-%d')
            agendamento = {
                'id': str(uuid.uuid4())[:8].upper(),
                'nome': d['nome'], 'email': d['email'],
                'telefone': d['telefone'], 'data': d['data'],
                'data_formatada': fmt_data_longa(d['data']),
                'horario': d['horario'],
                'motivo': d.get('motivo',''),
                'status': 'confirmado',
                'criado_em': datetime.now().isoformat()
            }
            agendamentos = load_agendamentos()
            # Checar disponibilidade
            disponiveis = horarios_disponiveis(d['data'])
            if d['horario'] not in disponiveis:
                return jsonify({'resposta': '⚠️ Esse horário foi ocupado. Escolha outro.', 'opcoes': [], 'acao': 'mostrar_horarios', 'data': d['data']})
            agendamentos.append(agendamento)
            save_agendamentos(agendamentos)
            enviar_email(agendamento)
            enviar_telegram(agendamento)
            enviar_whatsapp(agendamento)
            estado['etapa'] = 'menu'; estado['dados'] = {}; salvar()
            acao = "Reagendamento" if d.get('reagendar_id') else "Agendamento"
            return jsonify({
                'resposta': f"🎉 *{acao} confirmado!*\n\n"
                           f"ID: *{agendamento['id']}*\n"
                           f"📅 {agendamento['data_formatada']}\n"
                           f"⏰ {agendamento['horario']}\n\n"
                           f"A {config['psianalista_nome']} foi notificada via WhatsApp. 📱\nGuarde seu ID!",
                'opcoes': ['📋 Meu histórico','↩️ Menu principal']
            })
        else:
            estado['etapa'] = 'menu'; estado['dados'] = {}; salvar()
            return jsonify({'resposta': 'Tudo bem! Posso ajudar com mais algo?', 'opcoes': ['📅 Agendar consulta','↩️ Menu principal']})

    # Fallback
    return jsonify({
        'resposta': 'Não entendi. Escolha uma opção:',
        'opcoes': ['📅 Agendar consulta','📋 Meu histórico','🔍 Verificar agendamento',
                   '🔄 Reagendar consulta','❌ Cancelar consulta','ℹ️ Sobre a clínica']
    })

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    load_config()
    print("\n🌿 Encaixamente — Clínica de Psicanálise")
    print("   Acesse: http://localhost:5000\n")
    app.run(debug=True, port=5000)
