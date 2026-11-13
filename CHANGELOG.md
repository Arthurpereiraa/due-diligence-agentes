# Changelog

## [0.1.1] - 2026-11-13

### Melhorado
- Redator recebe recomendações concretas derivadas dos alertas, em vez de criar recomendações genéricas.
- Prompt do redator proíbe título no início e comentários sobre assuntos que os dados não cobrem.
- Revisor detecta por código termos sem base nos dados (ex.: "estabilidade financeira", "funcionários"),
  título no início e quantidade de recomendações fora de 2 a 4.
- Teste de regressão com o parecer real gerado pelo llama3.2:3b no primeiro uso.

## [0.1.0] - 2026-11-13

### Adicionado
- Agentes coletor, analista, redator, revisor e investigador, coordenados por um orquestrador.
- Ciclo redator ⇄ revisor com verificação determinística de fatos e revisão por LLM.
- Cliente MCP (stdio) e cliente Ollama sem dependências externas.
- CLI `diligencia` com os comandos `analisar`, `perguntar` e `ferramentas`.
- Testes com servidor MCP falso e LLM roteirizado; integração opcional com o mcp-brasil real.
