# Changelog

## [0.1.0] - 2026-11-13

### Adicionado
- Agentes coletor, analista, redator, revisor e investigador, coordenados por um orquestrador.
- Ciclo redator ⇄ revisor com verificação determinística de fatos e revisão por LLM.
- Cliente MCP (stdio) e cliente Ollama sem dependências externas.
- CLI `diligencia` com os comandos `analisar`, `perguntar` e `ferramentas`.
- Testes com servidor MCP falso e LLM roteirizado; integração opcional com o mcp-brasil real.
