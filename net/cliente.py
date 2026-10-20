"""Cliente del modo multijugador: se conecta al servidor, manda lo que hace el jugador y guarda
la última instantánea recibida. No simula nada: solo dibuja lo que dice el servidor."""
from __future__ import annotations

import socket
from typing import List, Optional

from net.protocolo import PUERTO, Canal


class Cliente:
    def __init__(self):
        self.canal: Optional[Canal] = None
        self.id: Optional[int] = None            # id de jugador que asignó el servidor
        self.estado: Optional[dict] = None       # última instantánea
        self.eventos: List[dict] = []            # efectos del nivel aún sin procesar
        self.error = ""

    @property
    def conectado(self) -> bool:
        return self.canal is not None and self.canal.abierto

    def conectar(self, direccion: str, nombre: str, puerto: int = PUERTO, espera: float = 3.0) -> bool:
        """Abre la conexión y se presenta. Devuelve False (y deja el motivo en .error) si falla."""
        try:
            sock = socket.create_connection((direccion, puerto), timeout=espera)
        except OSError as error:
            self.error = f"NO SE PUDO CONECTAR: {error.strerror or error}"[:60].upper()
            return False
        self.canal = Canal(sock)
        self.canal.enviar({"t": "hola", "nombre": nombre})
        return True

    def enviar(self, tipo: str, **datos) -> None:
        if self.conectado:
            self.canal.enviar(dict(t=tipo, **datos))

    def actualizar(self) -> None:
        """Lee lo que haya llegado. Se llama una vez por paso del juego."""
        if self.canal is None:
            return
        self.canal.vaciar()
        for m in self.canal.recibir():
            tipo = m.get("t")
            if tipo == "bienvenida":
                self.id = m["id"]
            elif tipo == "rechazo":
                self.error = m.get("motivo", "RECHAZADO")
            elif tipo == "estado":
                self.eventos += m.pop("eventos", [])    # los eventos no se pueden perder
                self.estado = m
        if not self.canal.abierto and not self.error:
            self.error = "SE PERDIÓ LA CONEXIÓN CON EL SERVIDOR"

    def cerrar(self) -> None:
        if self.canal is not None:
            self.canal.cerrar()
