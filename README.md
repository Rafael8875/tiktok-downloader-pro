# TikTok Downloader Pro 🎵

Uma plataforma web profissional para download de vídeos do TikTok, com interface premium, responsiva e pronta para deploy no Render.

## 🚀 Funcionalidades

- **Download de vídeos** em múltiplas qualidades (360p, 480p, 720p, 1080p)
- **Conversão para MP3** (128kbps, 192kbps, 320kbps)
- **Geração de GIF** com seleção de trecho (até 10 segundos)
- **Interface premium** com design escuro, vermelho e branco
- **Barra de progresso** em tempo real
- **Fila de downloads** com controle de concorrência
- **Histórico local** de downloads (localStorage)
- **Estatísticas** de uso
- **FAQ, Privacidade e Termos** integrados
- **Responsivo** para mobile e desktop
- **Rate limiting** para proteção do servidor
- **Proteção SSRF** e validação rigorosa de URLs
- **Limpeza automática** de arquivos temporários
- Deploy pronto para **Render**

## ⚠️ Aviso Legal

Esta ferramenta utiliza apenas métodos públicos (yt-dlp) para acessar conteúdo do TikTok. Ela **NÃO**:
- Contorna CAPTCHA ou autenticação
- Acessa vídeos privados
- Burla proteções anti-bot
- Usa APIs não autorizadas

Baixe apenas conteúdo que você tem direito de acessar. Respeite os direitos autorais e os termos de serviço do TikTok.

## 📋 Requisitos

- Python 3.9+
- FFmpeg (para conversão MP3 e GIF)

## 🛠️ Instalação Local

1. **Clone o repositório:**
```bash
git clone <URL_DO_REPOSITORIO>
cd tiktok-downloader-pro
```

2. **Crie um ambiente virtual:**
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

3. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

4. **Configure o `.env`:**
```bash
cp .env.example .env
```

5. **Execute:**
```bash
python run.py
```

6. **Acesse:** http://localhost:5000

## 🧪 Testes

```bash
python -m pytest tests/ -v
```

## 🌐 Deploy no Render

### Passo a Passo:

1. **Suba para o GitHub:**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <URL_DO_REPOSITORIO>
git push -u origin main
```

2. **No Render (render.com):**
   - Crie uma conta (se ainda não tiver)
   - Clique em **"New"** → **"Blueprint"**
   - Conecte o repositório GitHub
   - O `render.yaml` já configura tudo automaticamente:
     - Web Service Python
     - FFmpeg instalado via build script
     - Disco persistente de 1GB para downloads
     - Variáveis de ambiente geradas automaticamente

3. **Aguarde o build** (~3-5 minutos na primeira vez)

4. **Acesse a URL** fornecida pelo Render (ex: `https://tiktok-downloader-pro.onrender.com`)

### Configuração Manual (alternativa ao Blueprint):

1. **New Web Service** → conectar repo
2. **Runtime:** Python
3. **Build Command:** `./render-build.sh`
4. **Start Command:** `./start.sh`
5. **Environment Variables:**
   - `PYTHON_VERSION` = `3.11.6`
   - `SECRET_KEY` = (gerar valor aleatório)
   - `PORT` = `10000`
   - `FILE_EXPIRATION` = `900`
6. **Disk:** Criar disco de 1GB montado em `/opt/render/project/downloads`

## 📁 Estrutura do Projeto

```
tiktok-downloader-pro/
├── run.py                  # Entry point
├── requirements.txt        # Dependências Python
├── render.yaml             # Configuração do Render
├── render-build.sh         # Script de build
├── start.sh                # Script de inicialização
├── .env.example            # Variáveis de ambiente exemplo
├── .gitignore              # Arquivos ignorados pelo Git
├── downloads/              # Diretório de downloads (auto-limpo)
├── app/
│   ├── __init__.py         # App factory + cleanup thread
│   ├── routes.py           # Endpoints da API
│   ├── utils.py            # yt-dlp + FFmpeg + validação
│   ├── security.py         # SSRF + sanitização
│   └── templates/
│       └── index.html      # Frontend completo (SPA)
└── tests/
    ├── __init__.py
    └── test_app.py          # Testes automatizados
```

## 🔒 Segurança

- **Validação de URLs:** Apenas URLs do TikTok são aceitas
- **Proteção SSRF:** Bloqueia redirecionamento para IPs privados
- **Rate Limiting:** 30 análises/hora, 20 downloads/hora por IP
- **Concorrência:** Máximo 3 downloads simultâneos
- **Tamanho:** Limite de 100MB por arquivo
- **Limpeza:** Arquivos removidos automaticamente após 15 minutos
- **Logs seguros:** Sem exposição de dados sensíveis

## 📄 Licença

Este projeto é para uso pessoal e educacional. Respeite os direitos autorais.
