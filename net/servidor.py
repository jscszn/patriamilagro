"""Servidor del modo multijugador: acepta hasta 4 clientes por TCP y corre la sesión.

Arquitectura cliente-servidor con servidor AUTORITATIVO:

    cliente 1 --botones-->  +----------+  --estado-->  cliente 1
    cliente 2 --botones-->  | SERVIDOR |  --estado-->  cliente 2
    cliente 3 --votos---->  | (Sesion) |  --estado-->  cliente 3 ...

Un solo hilo atiende a todos con sockets NO bloqueantes: en cada vuelta (60 por segundo) acepta
conexiones nuevas, lee lo que haya llegado, avanza la sesión un paso y envía instantáneas.
No hace falta un hilo por cliente ni candados sobre el estado del juego.

Se puede usar de dos formas:
  - Dentro del juego: el anfitrión elige "CREAR PARTIDA" y el servidor corre en un hilo aparte.
  - Dedicado, sin ventana:   python -m net.servidor --puerto 50505
"""
from __future__ import annotations

import argparse
import socket
import threading
import time
from typing import Dict, Optional

import settings
from net import sesion as ss
from net.protocolo import PUERTO, Canal, ip_local
from net.sesion import Sesion

PASOS_POR_INSTANTANEA = {ss.NIVEL: 2}      # en el nivel: 30 instantáneas por segundo
INSTANTANEA_LENTA = 6                      # en las demás fases: 10 por segundo


class Servidor:
    def __init__(self, puerto: int = PUERTO, anfitrion: str = "0.0.0.0", sesion: Optional[Sesion] = None):
        self.sesion = sesion or Sesion()
        self.escucha = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.escucha.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.escucha.bind((anfitrion, puerto))
        self.escucha.listen(settings.MAX_JUGADORES + 2)
        self.escucha.setblocking(False)
        self.puerto = self.escucha.getsockname()[1]
        self.clientes: Dict[int, Canal] = {}          # id de jugador -> canal
        self.nuevos: list = []                        # canales que aún no dijeron "hola"
        self.corriendo = False
        self.hilo: Optional[threading.Thread] = None
        self.pasos = 0

    # --- Una vuelta del bucle ------------------------------------------------------------------
    def _aceptar(self) -> None:
        while True:
            try:
                sock, _ = self.escucha.accept()
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            self.nuevos.append(Canal(sock))

    def _presentaciones(self) -> None:
        """Los canales nuevos deben decir 'hola'; ahí reciben su id o un rechazo."""
        for canal in list(self.nuevos):
            for m in canal.recibir():
                if m.get("t") != "hola":
                    continue
                nuevo = self.sesion.unir(str(m.get("nombre", "")))
                self.nuevos.remove(canal)
                if nuevo is None:
                    canal.enviar({"t": "rechazo", "motivo": "SALA LLENA O PARTIDA EN CURSO"})
                    canal.cerrar()
                else:
                    self.clientes[nuevo] = canal
                    canal.enviar({"t": "bienvenida", "id": nuevo})
                break
            if not canal.abierto and canal in self.nuevos:
                self.nuevos.remove(canal)

    def _leer(self) -> None:
        for id_jugador, canal in list(self.clientes.items()):
            for m in canal.recibir():
                self.sesion.recibir(id_jugador, m)
            if not canal.abierto:                     # se desconectó
                del self.clientes[id_jugador]
                self.sesion.salir(id_jugador)

    def _difundir(self) -> None:
        cada = PASOS_POR_INSTANTANEA.get(self.sesion.fase, INSTANTANEA_LENTA)
        if self.pasos % cada == 0:
            instantanea = self.sesion.instantanea()
            for canal in self.clientes.values():
                canal.enviar(instantanea)
        else:
            for canal in self.clientes.values():
                canal.vaciar()                        # termina de mandar lo que quedó en cola

    def vuelta(self, dt: float = settings.DT) -> None:
        """Un paso completo: aceptar, leer, simular y enviar."""
        self._aceptar()
        self._presentaciones()
        self._leer()
        self.sesion.paso(dt)
        self.pasos += 1
        self._difundir()

    # --- Ciclo de vida ---------------------------------------------------------------------------
    def bucle(self) -> None:
        self.corriendo = True
        siguiente = time.perf_counter()
        while self.corriendo:
            self.vuelta()
            siguiente += settings.DT
            espera = siguiente - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            else:                                     # se atrasó: no intenta recuperar el tiempo perdido
                siguiente = time.perf_counter()
        self._cerrar()

    def iniciar_en_hilo(self) -> None:
        self.hilo = threading.Thread(target=self.bucle, name="servidor-patria", daemon=True)
        self.hilo.start()

    def detener(self) -> None:
        self.corriendo = False
        if self.hilo is not None and self.hilo is not threading.current_thread():
            self.hilo.join(timeout=1.0)
        elif self.hilo is None:
            self._cerrar()

    def _cerrar(self) -> None:
        for canal in list(self.clientes.values()) + self.nuevos:
            canal.cerrar()
        self.clientes, self.nuevos = {}, []
        try:
            self.escucha.close()
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor dedicado de Patria Milagro")
    parser.add_argument("--puerto", type=int, default=PUERTO)
    parser.add_argument("--minimo", type=int, default=2, help="jugadores necesarios para empezar")
    parser.add_argument("--arena", action="store_true", help="(desarrollo) los niveles empiezan en el jefe")
    args = parser.parse_args()
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")       # la física usa pygame.Rect, no una ventana
    servidor = Servidor(args.puerto, sesion=Sesion(minimo=args.minimo, en_arena=args.arena))
    print(f"Servidor de Patria Milagro en {ip_local()}:{servidor.puerto} (Ctrl+C para terminar)")
    try:
        servidor.bucle()
    except KeyboardInterrupt:
        servidor.corriendo = False
        servidor._cerrar()


if __name__ == "__main__":
    main()
