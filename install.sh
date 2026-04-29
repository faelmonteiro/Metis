#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
GOLD='\033[38;5;214m'
DIM_GOLD='\033[38;5;136m'
CYAN='\033[0;36m'

INSTALL_DIR="$HOME/.local/share/ai-terminal-assistant"
FILES=("ai_core.sh" "ai_assistant.sh")

cd "$(dirname "$0")" || exit

clear
echo -e "${DIM_GOLD}"
echo -e "  ███╗   ███╗███████╗████████╗██╗███████╗"
echo -e "  ████╗ ████║██╔════╝╚══██╔══╝██║██╔════╝"
echo -e "  ██╔████╔██║█████╗     ██║   ██║███████╗"
echo -e "  ██║╚██╔╝██║██╔══╝     ██║   ██║╚════██║"
echo -e "  ██║ ╚═╝ ██║███████╗   ██║   ██║███████║"
echo -e "  ╚═╝     ╚═╝╚══════╝   ╚═╝   ╚═╝╚══════╝${NC}"
echo -e "${GOLD}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GOLD}   Assistente inteligente para o terminal  ${NC}"
echo -e "${GOLD}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e ""

echo -e "\n${YELLOW}[Passo 1/4] Verificando Dependências${NC}"
deps=("curl" "jq" "fzf")
for dep in "${deps[@]}"; do
    if ! command -v "$dep" &> /dev/null; then
        echo -e "${YELLOW}Instalando $dep...${NC}"
        if command -v pacman &> /dev/null; then sudo pacman -S --needed --noconfirm "$dep"
        elif command -v apt &> /dev/null; then sudo apt update && sudo apt install -y "$dep"
        elif command -v dnf &> /dev/null; then sudo dnf install -y "$dep"
        elif command -v zypper &> /dev/null; then sudo zypper install -y "$dep"
        else
            echo -e "${RED}❌ Erro: Gerenciador de pacotes não reconhecido. Instale '$dep' manualmente.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✔ $dep já instalado${NC}"
    fi
done

echo -e "\n${YELLOW}[Passo 2/4] Configurando Inteligência Artificial${NC}"
if ! command -v ollama &> /dev/null; then
    echo -e "${BLUE}Instalando motor Ollama...${NC}"
    curl -fsSL https://ollama.com/install.sh | sh
fi

echo -e "${BLUE}Iniciando serviço Ollama...${NC}"

# Tenta iniciar via systemctl (pede senha e ESPERA completar)
if command -v systemctl &> /dev/null; then
    sudo systemctl start ollama 2>/dev/null
fi

# Se o systemctl falhou ou não existe, inicia manualmente
if ! curl -s --max-time 2 -o /dev/null http://localhost:11434/ 2>/dev/null; then
    ollama serve > /dev/null 2>&1 &
    echo -e "${YELLOW}Aguardando Ollama iniciar...${NC}"
    # Espera até o serviço responder (máx 15 segundos)
    for i in $(seq 1 15); do
        if curl -s --max-time 1 -o /dev/null http://localhost:11434/ 2>/dev/null; then
            break
        fi
        sleep 1
    done
fi

# Confirma se o Ollama está rodando
if curl -s --max-time 2 -o /dev/null http://localhost:11434/ 2>/dev/null; then
    echo -e "${GREEN}✔ Ollama está rodando${NC}"
else
    echo -e "${RED}⚠️ Ollama não respondeu. O download de modelos pode falhar.${NC}"
fi

# Menu Organizado por Necessidade de Hardware
echo -e "\n${BLUE}🤖 Escolha a IA que deseja baixar como PADRÃO:${NC}"
OPCOES="
qwen2.5-coder:7b    [Padrão 8GB+] Focado em programação e terminal
llama3.1:8b         [Padrão 8GB+] Uso geral com respostas complexas
deepseek-coder:6.7b [Padrão 8GB+] Alternativa forte para código
qwen2.5-coder:3b    [Leve 4GB-8GB] Menor consumo de memória
phi3:mini           [Leve 4GB-8GB] Otimizado para hardware modesto
Pular_Download      [Nenhum] Já tenho modelos baixados"

while true; do
    ESCOLHA=$(echo "$OPCOES" | fzf --height=40% --reverse --border --header="Selecione o modelo:")
    MODELO_ESCOLHIDO=$(echo "$ESCOLHA" | awk '{print $1}')

    if [[ -z "$MODELO_ESCOLHIDO" || "$MODELO_ESCOLHIDO" == "Pular_Download" ]]; then
        # Conta quantas linhas 'ollama list' retorna (a 1ª linha é o cabeçalho)
        QTD_MODELOS=$(ollama list 2>/dev/null | wc -l)
        
        if [ "$QTD_MODELOS" -gt 1 ]; then
            # Pega o nome do primeiro modelo instalado (linha 2, coluna 1)
            MODELO_ESCOLHIDO=$(ollama list | awk 'NR==2 {print $1}')
            echo -e "${GREEN}✔ Modelos locais encontrados. Configurando para usar: ${YELLOW}$MODELO_ESCOLHIDO${NC}"
            break
        else
            echo -e "\n${RED}⚠️ Você não possui nenhum modelo instalado! Por favor, escolha um modelo na lista.${NC}"
            sleep 2
            # O loop vai reiniciar e mostrar o menu fzf de novo
        fi
    else
        echo -e "${BLUE}Baixando $MODELO_ESCOLHIDO...${NC}"
        ollama pull "$MODELO_ESCOLHIDO"
        break
    fi
done

echo -e "\n${YELLOW}[Passo 3/4] Aplicando Configurações${NC}"
mkdir -p "$INSTALL_DIR"
echo "MODEL=\"$MODELO_ESCOLHIDO\"" > "$INSTALL_DIR/config.env"

missing_files=0
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$INSTALL_DIR/"
        chmod +x "$INSTALL_DIR/$file"
        echo -e "${GREEN}✔ $file instalado${NC}"
    else
        echo -e "${RED}❌ Erro: Arquivo '$file' não encontrado no diretório de instalação!${NC}"
        missing_files=1
    fi
done

if [ "$missing_files" -eq 1 ]; then
    echo -e "${RED}⚠️ Alguns arquivos não foram encontrados. Verifique se todos os arquivos estão no mesmo diretório do install.sh${NC}"
    exit 1
fi

echo -e "\n${YELLOW}[Passo 4/4] Integrando ao Terminal${NC}"
detect_shell_rc() { [[ "$SHELL" == *"zsh"* ]] && echo "$HOME/.zshrc" || echo "$HOME/.bashrc"; }
RC_FILE=$(detect_shell_rc)

if ! grep -q "ai_assistant.sh" "$RC_FILE"; then
    echo -e "\n# AI Terminal Assistant\nsource \"$INSTALL_DIR/ai_assistant.sh\"" >> "$RC_FILE"
fi

echo -e "\n${BLUE}============================================"
echo -e "${GREEN}🚀 INSTALAÇÃO CONCLUÍDA!${NC}"
echo -e "Modelo ativo: ${YELLOW}$MODELO_ESCOLHIDO${NC}"
echo -e "Para ativar agora: ${YELLOW}source $RC_FILE${NC}"
echo -e "${BLUE}============================================${NC}"
