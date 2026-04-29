#!/bin/bash

# 1. Importação do Núcleo
SOURCE_DIR="$(dirname "${BASH_SOURCE[0]:-$0}")"
source "$SOURCE_DIR/ai_core.sh"

# 2. Funções Auxiliares de Interface
log_metis() {
    if [ "$VERBOSE" != "false" ]; then echo -e "$1"; fi
}

# Insere comando no terminal e permite edição antes do Enter
fill_terminal_cmd() {
    local cmd="$1"
    if [ -n "$ZSH_VERSION" ]; then
        print -s "$cmd" # Salva no histórico
        print -z "$cmd" # Joga no prompt
    elif [ -n "$BASH_VERSION" ]; then
        history -s "$cmd"
        # O -e -i permite editar o texto sugerido
        read -e -i "$cmd" -p "➜ " final_cmd
        if [ -n "$final_cmd" ]; then
            eval "$final_cmd"
            history -s "$final_cmd"
        fi
    fi
}

# 3. Configuração de Modelos
ai_config() {
    if ! command -v ollama &> /dev/null; then echo -e "\e[31m❌ Erro: Ollama não encontrado.\e[0m"; return 1; fi
    echo -e "\e[34m🔍 Buscando modelos...\e[0m"
    local modelo_escolhido=$(ollama list | tail -n +2 | awk '{print $1}' | fzf --height=30% --reverse --border --header="🤖 Selecione a LLM para o Assistente:")
    
    if [ -n "$modelo_escolhido" ]; then
        mkdir -p "$HOME/.local/share/ai-terminal-assistant"
        echo "MODEL=\"$modelo_escolhido\"" > "$HOME/.local/share/ai-terminal-assistant/config.env"
        echo "VERBOSE=\"$VERBOSE\"" >> "$HOME/.local/share/ai-terminal-assistant/config.env"
        echo -e "\e[32m✅ Modelo atualizado para: \e[1m$modelo_escolhido\e[0m"
        MODEL="$modelo_escolhido"
    fi
}

# 4. Função do Atalho Ctrl+G
inteligencia_prompt() {
    local busca=$(echo "" | fzf --height=15% --reverse --border --header="🤖 IA ($MODEL): O que você precisa?" --print-query | head -n 1)

    if [ -z "$busca" ]; then
        [ -n "$ZSH_VERSION" ] && zle redisplay
        return
    fi

    local modo=$(echo -e "🚀 1. Executar Comando\n📚 0. Me Ensinar" | fzf --height=15% --reverse --border --header="Pergunta: $busca")

    if [[ "$modo" == *"1"* ]]; then
        log_metis "\n🤖 Gerando comando..."
        local prompt="Atue como terminal Linux ($OS_NAME). Pedido: '$busca'. Responda APENAS o comando bash. Sem explicações ou crases."
        local result=$(query_ollama "$prompt")
        local fixed=$(clean_cmd "$result")
        
        if [ -n "$BASH_VERSION" ]; then
            # No Bash injetamos direto na linha atual
            READLINE_LINE="${READLINE_LINE}${fixed}"
            READLINE_POINT=${#READLINE_LINE}
        else
            LBUFFER+="$fixed"
        fi
    elif [[ "$modo" == *"0"* ]]; then
        echo -e "\n\e[35m🎓 --- TUTORIAL $MODEL ---\e[0m"
        local prompt="Explique de forma breve e didática o comando para: '$busca'. Use exemplos."
        query_ollama "$prompt"
        echo -e "\e[35m------------------------\e[0m"
    fi
    [ -n "$ZSH_VERSION" ] && zle redisplay
}

# 5. Tratamento de Erros (Correção Automática)
ai_fix_handler() {
    local cmd="$1"
    log_metis "\e[33m⚠️ Comando não encontrado: $cmd\e[0m"
    log_metis "\e[34m🤖 Consultando $MODEL ($OS_NAME)...\e[0m"

    local prompt="Corrija o comando: $cmd
    Regras:
    NUNCA escreva introduções como 'Claro', 'Aqui está' ou 'O comando é'.
    Responda APENAS com o comando corrigido. Se houver mais de uma opção, liste como 1. comando1, 2. comando2. Sem explicações."

    local raw_result=$(query_ollama "$prompt")

    # Limpa a resposta: remove backticks, linhas vazias, espaços extras
    local result=$(echo "$raw_result" | tr -d '\r' | sed 's/`//g' | awk 'NF' | head -n 5)

    if [[ -z "$result" ]]; then
        echo -e "\e[31m❌ Nenhuma sugestão recebida.\e[0m"
        return 127
    fi

    echo -e "\n\e[36m$result\e[0m\n"

    # Conta quantas linhas numeradas existem (padrão: 1. ou 1))
    local max_opt=$(echo "$result" | grep -cE '^[0-9]+[.\)]')

    if [ "$max_opt" -gt 1 ]; then
        # Múltiplas opções numeradas
        echo -n -e "\e[33mEscolha o número (1-$max_opt) para preencher, ou Enter para cancelar: \e[0m"
        read -r escolha

        if [[ -z "$escolha" ]]; then
            return 0
        fi

        if [[ "$escolha" =~ ^[0-9]+$ ]] && [ "$escolha" -ge 1 ] && [ "$escolha" -le "$max_opt" ]; then
            local chosen=$(echo "$result" | grep -E "^${escolha}[.\)]" | sed -E 's/^[0-9]+[.\)]\s*//' | xargs)
            chosen=$(clean_cmd "$chosen")
            if [[ -n "$chosen" ]]; then
                if [[ "$chosen" =~ (^|[[:space:]])(rm|mkfs|dd|fdisk|parted|chown|chmod|shred)([[:space:]]|$) ]]; then
                    echo -e "\e[41m\e[97m 🚨 CUIDADO: COMANDO DESTRUTIVO! \e[0m"
                fi
                fill_terminal_cmd "$chosen"
            fi
        else
            echo -e "\e[31m❌ Opção inválida.\e[0m"
            return 1
        fi
    else
        # Comando único (limpa numeração caso a IA tenha colocado "1." mesmo assim)
        local single_cmd=$(echo "$result" | sed -E 's/^[0-9]+[.\)]\s*//' | tail -n 1 | xargs)
        single_cmd=$(clean_cmd "$single_cmd")

        if [[ -n "$single_cmd" ]]; then
            if [[ "$single_cmd" =~ (^|[[:space:]])(rm|mkfs|dd|fdisk|parted|chown|chmod|shred)([[:space:]]|$) ]]; then
                echo -e "\e[41m\e[97m 🚨 CUIDADO: COMANDO DESTRUTIVO! \e[0m"
            fi
            echo -n "Preencher? (S/n): "
            read -r choice
            [[ "$choice" =~ ^[sS]?$ ]] && fill_terminal_cmd "$single_cmd"
        fi
    fi
}


# Atalhos e Handlers
if [ -n "$ZSH_VERSION" ]; then
    command_not_found_handler() { ai_fix_handler "$*"; return 0; }
    zle -N inteligencia_prompt
    bindkey '^G' inteligencia_prompt
elif [ -n "$BASH_VERSION" ]; then
    command_not_found_handle() { ai_fix_handler "$*"; return 0; }
    bind -x '"\C-g": "inteligencia_prompt"'
fi