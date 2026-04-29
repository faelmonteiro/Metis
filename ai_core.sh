#!/bin/bash

# 1. Identidade e Sistema
# Detecta o sistema operacional para dar contexto exato à IA
OS_NAME=$(grep '^PRETTY_NAME=' /etc/os-release | cut -d '=' -f 2 | tr -d '"')

# 2. Configurações e Persistência
INSTALL_DIR="$HOME/.local/share/ai-terminal-assistant"
CONFIG_FILE="$INSTALL_DIR/config.env"
OLLAMA_URL="http://localhost:11434/api/generate"

# Carrega configurações do usuário (Modelo e Modo Verbose)
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    MODEL="qwen2.5-coder:7b"
    VERBOSE="true"
fi

# 3. Verificações de Saúde do Sistema
check_dependencies() {
    if ! command -v jq &> /dev/null; then
        echo -e "\e[31m[!] Erro crítico: 'jq' não encontrado. O METIS precisa dele.\e[0m"
        return 1
    fi
}

ollama_online() {
    # Timeout de 2 segundos para não travar o terminal se o Ollama estiver desligado
    curl -s --max-time 2 -o /dev/null -w "%{http_code}" "http://localhost:11434/" 2>/dev/null | grep -q "200"
}

# 4. Comunicação com a IA
query_ollama() {
    check_dependencies || return 1
    
    if ! ollama_online; then
        # Se o modo silencioso estiver desligado, avisa que o Ollama falhou
        if [ "$VERBOSE" != "false" ]; then
            echo -e "\e[31m[!] Erro: Ollama offline.\e[0m"
        fi
        return 1
    fi

    local prompt="$1"
    
    # Monta o JSON de forma segura usando jq (evita erros com aspas no prompt)
    local json_payload
    json_payload=$(jq -n --arg model "$MODEL" --arg prompt "$prompt" \
        '{model: $model, prompt: $prompt, stream: false}')

    local response
    response=$(curl -s -X POST "$OLLAMA_URL" -d "$json_payload" -H "Content-Type: application/json" 2>/dev/null)

    # Valida se a resposta é um JSON válido e não contém erros do Ollama
    if [ -z "$response" ] || echo "$response" | jq -e '.error' >/dev/null 2>&1; then
        return 1
    fi

    # Extrai apenas o texto da resposta
    echo "$response" | jq -r '.response // empty'
}

# 5. Tratamento de Texto
clean_cmd() {
    # Remove crases, nomes de shells e espaços extras nas pontas, PRESERVANDO espaços internos
    # head -n 1 garante retorno de uma única linha (evita quebra no READLINE_LINE)
    echo "$1" | sed 's/`//g' | sed '/^bash$/d' | sed '/^zsh$/d' | sed '/^$/d' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | head -n 1
}