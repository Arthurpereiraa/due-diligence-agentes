import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from due_diligence.llm import LLMError, OllamaLLM, ferramentas_mcp_para_llm


class OllamaFalso:
    """Servidor HTTP mínimo que imita o endpoint /api/chat do Ollama."""

    def __init__(self, status=200, resposta=None):
        self.recebido = None
        falso = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                falso.recebido = (self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = json.dumps(resposta if status == 200 else {"error": "model 'x' not found"}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def fechar(self):
        self.server.shutdown()


def test_envia_payload_e_le_tool_calls():
    resposta = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "consultar_cep", "arguments": {"cep": "01310100"}}},
                {"function": {"name": "consultar_ddd", "arguments": '{"ddd": "11"}'}},
            ],
        }
    }
    falso = OllamaFalso(resposta=resposta)
    try:
        llm = OllamaLLM(modelo="qwen2.5:7b", host=falso.url)
        tools = ferramentas_mcp_para_llm([{"name": "consultar_cep", "description": "d", "inputSchema": {"type": "object"}}])
        r = llm.chat([{"role": "user", "content": "oi"}], tools=tools, json_mode=True)
    finally:
        falso.fechar()

    path, payload = falso.recebido
    assert path == "/api/chat"
    assert payload["model"] == "qwen2.5:7b"
    assert payload["stream"] is False
    assert payload["format"] == "json"
    assert payload["tools"][0]["function"]["name"] == "consultar_cep"
    assert [(c.name, c.arguments) for c in r.tool_calls] == [
        ("consultar_cep", {"cep": "01310100"}),
        ("consultar_ddd", {"ddd": "11"}),
    ]
    assert llm.nome == "ollama/qwen2.5:7b"


def test_modelo_inexistente_sugere_pull():
    falso = OllamaFalso(status=404)
    try:
        with pytest.raises(LLMError, match="ollama pull llama3.1"):
            OllamaLLM(modelo="llama3.1", host=falso.url).chat([{"role": "user", "content": "oi"}])
    finally:
        falso.fechar()


def test_ollama_desligado_da_erro_claro():
    with pytest.raises(LLMError, match="Ele está aberto"):
        OllamaLLM(host="http://127.0.0.1:9", timeout=2).chat([{"role": "user", "content": "oi"}])


def test_configuracao_por_variaveis(monkeypatch):
    monkeypatch.setenv("DILIGENCIA_MODELO", "llama3.2")
    monkeypatch.setenv("OLLAMA_HOST", "192.168.0.10:11434")
    llm = OllamaLLM()
    assert llm.modelo == "llama3.2"
    assert llm.host == "http://192.168.0.10:11434"
