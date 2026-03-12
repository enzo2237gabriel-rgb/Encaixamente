# 🌿 Encaixamente — Sistema de Agendamento

Sistema completo de agendamento online para a Clínica de Psicanálise **Encaixamente**.

---

## 📁 Estrutura do projeto

```
encaixamento/
├── app.py                 # Servidor Flask principal
├── requirements.txt       # Dependências Python
├── data/
│   ├── agendamentos.json  # Banco de dados local (criado automaticamente)
│   └── config.json        # Configurações da clínica (criado automaticamente)
└── templates/
    ├── index.html         # Página inicial com bot de chat
    ├── agendar.html       # Formulário de agendamento (3 etapas)
    └── admin.html         # Painel administrativo
```

---

## 🚀 Como rodar

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Rodar o servidor

```bash
python app.py
```

### 3. Acessar no navegador

- **Site principal:** http://localhost:5000
- **Agendamento:** http://localhost:5000/agendar
- **Painel admin:** http://localhost:5000/admin

---

## ⚙️ Configuração de notificações

Acesse **http://localhost:5000/admin** e clique em "Configurações" para definir:

### 📧 E-mail (Gmail)
1. Crie uma [Senha de App no Gmail](https://myaccount.google.com/apppasswords)
2. Preencha:
   - **E-mail remetente:** seu Gmail
   - **Senha de app:** a senha gerada (16 caracteres)
   - **E-mail destino:** e-mail da psicanalista

### 📱 WhatsApp (Twilio) — **Recomendado**
1. Crie conta gratuita em [twilio.com](https://www.twilio.com)
2. No painel, vá em **Messaging → Try it out → Send a WhatsApp message**
3. Ative o **sandbox**: a psicanalista envia `join <palavra>` para o número do sandbox
4. Copie o **Account SID** e **Auth Token** do painel principal
5. No campo *"from"*, use o número do sandbox: `whatsapp:+14155238886`
6. No campo *"to"*, coloque o WhatsApp da psicanalista: `whatsapp:+5585XXXXXXXXX`

1. Crie um bot com [@BotFather](https://t.me/BotFather) → `/newbot`
2. Copie o **token** do bot
3. A psicanalista deve iniciar conversa com o bot
4. Acesse `https://api.telegram.org/bot<TOKEN>/getUpdates` para obter o **Chat ID**
5. Preencha os dois campos no painel admin

---

## 🤖 Funcionalidades do Bot

O assistente virtual no chat da página principal permite:
- ✅ **Agendar consulta** (fluxo guiado passo a passo)
- 🔍 **Verificar agendamento** por ID
- ❌ **Cancelar consulta** por ID + e-mail

---

## 📋 Funcionalidades

| Feature | Descrição |
|---|---|
| 🗓️ Calendário interativo | Seleção visual de datas com dias disponíveis |
| ⏰ Horários em tempo real | Mostra apenas horários não ocupados |
| 🤖 Bot de chat | Assistente que guia o agendamento |
| 📧 Notificação por e-mail | E-mail HTML formatado para a psicanalista |
| 📱 Notificação Telegram | Mensagem instantânea no Telegram |
| 🔒 Cancelamento seguro | Cancelamento por ID + e-mail |
| 🛠️ Painel admin | Visualização de agenda e configurações |

---

## 🔧 Personalização dos horários

Edite o arquivo `data/config.json` ou use o painel admin.

Para adicionar/remover horários de cada dia da semana, edite `horarios_disponiveis` no config.json:

```json
"horarios_disponiveis": {
  "segunda": ["09:00", "10:00", "11:00", "14:00", "15:00"],
  "terca":   ["09:00", "10:00", "11:00", "14:00"],
  ...
}
```

---

Desenvolvido com 💛 para a Clínica Encaixamente
