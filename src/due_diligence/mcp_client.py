"""Cliente MCP mínimo (JSON-RPC 2.0 sobre stdio), só com a biblioteca padrão.

Sobe o servidor como subprocesso, faz o handshake (`initialize`) e expõe `list_tools` e `call_tool`.
Spec: https://modelcontextprotocol.io/specification
"""

from __future__ import annotations

import json
import os
import queue
import shlex
import shutil
import subprocess
import threading
from typing import Any

from due_diligence import __version__

PROTOCOL_VERSION = "2025-06-18"


class McpError(RuntimeError):
    """Falha de comunicação ou erro de protocolo com o servidor MCP."""


class ToolError(McpError):
    """A ferramenta rodou, mas devolveu erro (`isError: true`), como um CNPJ não encontrado."""


def comando_padrao() -> list[str]:
    """Comando que sobe o mcp-brasil. `MCP_BRASIL_CMD` sobrescreve (ex.: "node ../mcp-brasil/dist/index.js")."""
    custom = os.environ.get("MCP_BRASIL_CMD")
    if custom:
        return shlex.split(custom, posix=os.name != "nt")
    # No Windows, `which` encontra o npx.cmd com o caminho completo, que o subprocess consegue executar.
    return [shutil.which("npx") or "npx", "-y", "mcp-brasil@0"]


class McpClient:
    def __init__(self, command: list[str] | None = None, timeout: float = 60.0) -> None:
        self.command = command or comando_padrao()
        self.timeout = timeout
        self._proc: subprocess.Popen[str] | None = None
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._next_id = 1
        self.server_info: dict[str, Any] = {}
        self._tools_cache: list[dict[str, Any]] | None = None

    # ciclo de vida -----------------------------------------------------------------

    def start(self) -> McpClient:
        try:
            self._proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",  # um byte inválido não pode derrubar a leitura
                bufsize=1,
                # Servidores em Python no Windows escrevem em cp1252 por padrão; força UTF-8.
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except FileNotFoundError as exc:
            raise McpError(
                f"Não encontrei o comando {self.command[0]!r}. Instale o Node.js 20+ ou defina MCP_BRASIL_CMD."
            ) from exc

        threading.Thread(target=self._read_stdout, daemon=True).start()
        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "due-diligence-agentes", "version": __version__},
            },
        )
        self.server_info = result.get("serverInfo", {})
        self._notify("notifications/initialized")
        return self

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
                self._proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self._proc.kill()
        self._proc = None

    def __enter__(self) -> McpClient:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # API -------------------------------------------------------------------------

    def list_tools(self) -> list[dict[str, Any]]:
        if self._tools_cache is None:
            self._tools_cache = self._request("tools/list", {}).get("tools", [])
        return self._tools_cache

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Chama a ferramenta e devolve o texto da resposta. Levanta ToolError se ela responder com erro."""
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        text = "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        if result.get("isError"):
            raise ToolError(text or f"A ferramenta {name} retornou erro.")
        return text

    def call_json(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        text = self.call_tool(name, arguments)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise McpError(f"Resposta de {name} não é JSON: {text[:200]}") from exc

    # transporte ------------------------------------------------------------------

    def _read_stdout(self) -> None:
        assert self._proc and self._proc.stdout
        try:
            for line in self._proc.stdout:
                self._lines.put(line)
        except (OSError, ValueError):
            pass  # pipe fechado
        finally:
            self._lines.put(None)  # fim do processo: destrava quem estiver esperando

    def _send(self, message: dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin or self._proc.poll() is not None:
            raise McpError("O servidor MCP não está rodando.")
        try:
            self._proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            self._proc.stdin.flush()
        except OSError as exc:
            raise McpError(f"Falha ao enviar mensagem ao servidor MCP: {exc}") from exc

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, **({"params": params} if params else {})})

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            while True:
                try:
                    line = self._lines.get(timeout=self.timeout)
                except queue.Empty as exc:
                    raise McpError(f"O servidor MCP não respondeu a {method} em {self.timeout:.0f}s.") from exc
                if line is None:
                    raise McpError("O servidor MCP encerrou inesperadamente.")
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue  # linha que não é JSON-RPC
                if message.get("id") != request_id:
                    continue  # notificação ou resposta de outra requisição
                if "error" in message:
                    raise McpError(f"{method}: {message['error'].get('message', message['error'])}")
                return message.get("result", {})
